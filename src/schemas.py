"""Single source of truth for every JSON schema. Other modules import from here, never redefine fields.

Schema notes
- `confidence` is a float in [0, 1]. Array entries carry ONE confidence per entry (v1 tradeoff).
- The design spec showed the transcript/certificate `fields` wrapper without its opening line;
  it is implemented here identically to the resume schema (document -> "fields" -> ...).
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Generic, List, Literal, Optional, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, Field, TypeAdapter

T = TypeVar("T")
Conf = Annotated[float, Field(ge=0.0, le=1.0)]


class DocType(str, Enum):
    resume = "resume"
    transcript = "transcript"
    certificate = "certificate"


class ModelName(str, Enum):
    donut = "donut"
    layoutlmv3 = "layoutlmv3"
    prompted_vlm = "prompted_vlm"


class Scored(BaseModel, Generic[T]):
    """A value plus the model's confidence in it."""
    value: Optional[T] = None
    confidence: Conf = 0.0


# ---- array entries (one confidence per entry) -------------------------------
class EducationEntry(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[str] = None
    confidence: Conf = 0.0


class ExperienceEntry(BaseModel):
    role: Optional[str] = None
    company: Optional[str] = None
    duration: Optional[str] = None
    confidence: Conf = 0.0


class ProjectEntry(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    confidence: Conf = 0.0


class SemesterMark(BaseModel):
    semester: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[str] = None
    confidence: Conf = 0.0


def _s():
    return Scored[str]()


# ---- per-type field sets ----------------------------------------------------
class ResumeFields(BaseModel):
    name: Scored[str] = Field(default_factory=_s)
    email: Scored[str] = Field(default_factory=_s)
    phone: Scored[str] = Field(default_factory=_s)
    skills: Scored[List[str]] = Field(default_factory=lambda: Scored[List[str]](value=[]))
    education: List[EducationEntry] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)


class TranscriptFields(BaseModel):
    institution: Scored[str] = Field(default_factory=_s)
    cgpa: Scored[float] = Field(default_factory=lambda: Scored[float]())
    semester_marks: List[SemesterMark] = Field(default_factory=list)


class CertificateFields(BaseModel):
    issuer: Scored[str] = Field(default_factory=_s)
    issue_date: Scored[str] = Field(default_factory=_s)
    recipient_name: Scored[str] = Field(default_factory=_s)
    signature_detected: Scored[bool] = Field(default_factory=lambda: Scored[bool]())
    stamp_detected: Scored[bool] = Field(default_factory=lambda: Scored[bool]())


# ---- full documents ----------------------------------------------------------
class _DocBase(BaseModel):
    doc_id: str
    version: int = Field(ge=1)
    extraction_model: ModelName
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResumeDoc(_DocBase):
    document_type: Literal["resume"] = "resume"
    fields: ResumeFields = Field(default_factory=ResumeFields)


class TranscriptDoc(_DocBase):
    document_type: Literal["transcript"] = "transcript"
    fields: TranscriptFields = Field(default_factory=TranscriptFields)


class CertificateDoc(_DocBase):
    document_type: Literal["certificate"] = "certificate"
    fields: CertificateFields = Field(default_factory=CertificateFields)


ExtractionDoc = Annotated[Union[ResumeDoc, TranscriptDoc, CertificateDoc],
                          Field(discriminator="document_type")]
_ADAPTER = TypeAdapter(ExtractionDoc)

FIELDS_MODEL = {"resume": ResumeFields, "transcript": TranscriptFields, "certificate": CertificateFields}

# Fields a Donut/LayoutLM question-answering baseline can fill (single-span text answers).
# Arrays, skills and signature/stamp detection are VLM-only in v1.
SCALAR_FIELDS = {
    "resume": ["name", "email", "phone"],
    "transcript": ["institution", "cgpa"],
    "certificate": ["issuer", "issue_date", "recipient_name"],
}

FIELD_QUESTIONS = {
    "name": "What is the full name of the person?",
    "email": "What is the email address?",
    "phone": "What is the phone number?",
    "institution": "What is the name of the university or institution?",
    "cgpa": "What is the CGPA or overall grade?",
    "issuer": "Which organization issued this certificate?",
    "issue_date": "What is the date of issue?",
    "recipient_name": "What is the name of the recipient?",
}


def parse_extraction(data: dict):
    """Validate a dict into the right *Doc model (discriminated on document_type)."""
    return _ADAPTER.validate_python(data)


def build_doc(doc_id: str, version: int, doc_type: str, model: str, fields: dict):
    """Build + validate a document; missing fields fall back to empty values with confidence 0."""
    return parse_extraction({"doc_id": doc_id, "version": version, "document_type": doc_type,
                             "extraction_model": model, "fields": fields or {}})


def schema_example(doc_type: str) -> dict:
    """A filled-in-shape template (including one example entry per array) used to prompt the VLM."""
    cls = FIELDS_MODEL[doc_type]
    out = cls().model_dump()
    for name, info in cls.model_fields.items():
        ann = info.annotation
        if get_origin(ann) is list:
            out[name] = [get_args(ann)[0]().model_dump()]
    return out


# ---- metadata + API models -----------------------------------------------------
class DocumentMetadata(BaseModel):
    doc_id: str
    version: int
    filename: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    document_type: Optional[DocType] = None
    classifier_confidence: Optional[float] = None
    extraction_model: Optional[ModelName] = None
    extracted_at: Optional[datetime] = None


class UploadResponse(BaseModel):
    doc_id: str
    version: int


class VersionsResponse(BaseModel):
    doc_id: str
    versions: List[DocumentMetadata]


class QueryRequest(BaseModel):
    question: str
    doc_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)


class Source(BaseModel):
    doc_id: str
    version: int
    text: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]


class ATSRequest(BaseModel):
    doc_id: str
    version: Optional[int] = None


class ATSResponse(BaseModel):
    ats_score: int
    reasons: List[str]
