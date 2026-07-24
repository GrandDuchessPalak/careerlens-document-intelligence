"""
schemas.py

Single source of truth for every document JSON schema used across the
CareerLens pipeline (extraction, storage, API, RAG). Every other module
imports from here — never redefine or hand-roll these fields elsewhere,
or the schema will silently drift out of sync across the codebase.

Design notes (see /areas/flagship-cv-project schema freeze for full context):
- `ConfidentValue[T]` is the reusable wrapper for any single extracted
  scalar/list field paired with the model's confidence in it.
- Array-of-record fields (education, experience, projects, semester marks)
  carry ONE confidence per entry, covering the whole record — not one
  confidence per sub-field. This is a deliberate v1 simplicity tradeoff,
  not an oversight.
- `extraction_model` and `document_type` are the same enums everywhere.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, List, Literal, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

T = TypeVar("T")


class ConfidentValue(BaseModel, Generic[T]):
    """A single extracted value paired with the model's confidence in it."""

    model_config = ConfigDict(frozen=True)

    value: T
    confidence: float = Field(ge=0.0, le=1.0)


ExtractionModel = Literal["donut", "layoutlmv3", "prompted_vlm"]
DocumentType = Literal["resume", "transcript", "certificate"]


class DocumentEnvelope(BaseModel):
    """
    Common envelope shared by every extracted document, regardless of
    type. Document-type-specific models inherit this and add their own
    `fields` payload — this is the composition point that lets new
    document types be added later without touching existing ones.
    """

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    version: int = Field(ge=1)
    document_type: DocumentType
    extraction_model: ExtractionModel
    extracted_at: datetime


# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

class EducationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degree: str
    institution: str
    year: str
    confidence: float = Field(ge=0.0, le=1.0)


class ExperienceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    company: str
    duration: str
    confidence: float = Field(ge=0.0, le=1.0)


class ProjectEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)


class ResumeFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ConfidentValue[str]
    email: ConfidentValue[str]
    phone: ConfidentValue[str]
    skills: ConfidentValue[List[str]]
    education: List[EducationEntry] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)


class ResumeDocument(DocumentEnvelope):
    document_type: Literal["resume"] = "resume"
    fields: ResumeFields


# ---------------------------------------------------------------------------
# Transcript / Marksheet
# ---------------------------------------------------------------------------

class SemesterMarkEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semester: str
    subject: str
    grade: str
    confidence: float = Field(ge=0.0, le=1.0)


class TranscriptFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_name: ConfidentValue[str]
    institution: ConfidentValue[str]
    cgpa: ConfidentValue[float]
    semester_marks: List[SemesterMarkEntry] = Field(default_factory=list)


class TranscriptDocument(DocumentEnvelope):
    document_type: Literal["transcript"] = "transcript"
    fields: TranscriptFields


# ---------------------------------------------------------------------------
# Certificate
# ---------------------------------------------------------------------------

class CertificateFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ConfidentValue[str]
    issuer: ConfidentValue[str]
    issue_date: ConfidentValue[str]
    recipient_name: ConfidentValue[str]
    signature_detected: ConfidentValue[bool]
    stamp_detected: ConfidentValue[bool]


class CertificateDocument(DocumentEnvelope):
    document_type: Literal["certificate"] = "certificate"
    fields: CertificateFields


# ---------------------------------------------------------------------------
# Union type + dispatch helper
# ---------------------------------------------------------------------------

AnyDocument = Union[ResumeDocument, TranscriptDocument, CertificateDocument]

_DOCUMENT_TYPE_MODELS: dict[DocumentType, type[BaseModel]] = {
    "resume": ResumeDocument,
    "transcript": TranscriptDocument,
    "certificate": CertificateDocument,
}


def parse_document(document_type: DocumentType, data: dict) -> AnyDocument:
    """
    Parse raw extraction output (or any incoming dict — API request body,
    storage read, etc.) into the correctly typed document model based on
    `document_type`.

    Use this at every ingestion boundary instead of instantiating a
    specific *Document model directly, so adding a new document type
    later only requires one new entry in _DOCUMENT_TYPE_MODELS, not a
    change at every call site.
    """

    model = _DOCUMENT_TYPE_MODELS.get(document_type)
    if model is None:
        raise ValueError(f"Unknown document_type: {document_type!r}")
    return model.model_validate(data)