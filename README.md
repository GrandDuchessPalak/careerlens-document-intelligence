# CareerLens — Multimodal Student Document Intelligence Platform

CareerLens is a document understanding system that classifies, extracts, and enables natural-language Q&A over three student-relevant document types — **resumes, transcripts/marksheets, and certificates** — by benchmarking OCR-free and OCR-dependent vision-language models and analyzing where each one fails.

## Why this project exists

Most "AI resume project" builds either (a) wrap an LLM API around a single document type with no real vision component, or (b) claim a novel CNN+Transformer architecture that can't be verified without real ablation infrastructure. CareerLens does neither.

Instead, it treats document understanding as a genuine research problem: benchmark existing state-of-the-art models (Donut vs. LayoutLMv3) on a domain with no public dataset, systematically categorize their failure modes, and use the results to justify *when* to fine-tune vs. *when* to fall back to zero-shot prompted extraction. That comparative study — not a bespoke architecture — is the project's real technical contribution.

**Research contribution statement:** Systematically benchmark OCR-free and OCR-dependent document understanding approaches on student-centric documents, analyze failure cases, and evaluate the effectiveness of prompt-based extraction for low-resource document domains.

## What it does (v1 scope)

- Accepts an uploaded resume, transcript, or certificate (PDF or image)
- Classifies the document type
- Extracts structured JSON, with a per-field confidence score
- Benchmarks two extraction approaches — **Donut** (OCR-free, encoder-decoder) and **LayoutLMv3** (OCR-dependent) — against each other on accuracy, latency, and memory
- Falls back to a prompted vision-language model (e.g. Qwen2.5-VL) for fields with no labeled training data
- Reports evaluation metrics and a qualitative error analysis (handwriting, low-res scans, skewed pages, stamps, signatures, embedded tables, missing fields)
- Supports document Q&A through a RAG pipeline
- Ships with a minimal web interface

Everything else — ATS scoring, JD matching, career recommendations, interview question generation — is a v2 enhancement built on top of the same extracted JSON, and does not block v1 completion.

## Why these 3 document types

Certificates and transcripts carry real visual complexity — stamps, signatures, seals, inconsistent institutional layouts — that justifies an actual vision component rather than a text-only pipeline. Resumes are mostly text but the document recruiters care about most. Together they tell one coherent story ("an AI assistant for a student's documents") without needing ten separate pipelines.

## Architecture

```
Frontend (React/Streamlit)
        │
        ▼
   FastAPI (api/)
        │
        ▼
  Preprocessing (PDF → image, resize/enhance)
        │
        ▼
  Doc Type Classifier (RVL-CDIP-based)
        │
        ▼
  Extraction (Donut / LayoutLMv3 / Prompted VLM)
        │
        ▼
  Storage Layer (document / metadata / json / embeddings)
        │
   ┌────┴─────┐
   ▼          ▼
RAG / Q&A   Intelligence layer (ATS, JD match, career recs — v2, all with explainability)
```

### End-to-end data flow
1. User uploads a document → assigned `doc_id`, versioned (`v1`, `v2`, ...)
2. Original file saved to `storage/documents/{doc_id}/{version}.pdf`
3. Preprocessing: PDF → image, resize/enhance
4. Doc type classifier tags it (resume / transcript / certificate)
5. Extraction pipeline (baseline Donut → fine-tuned if needed → prompted VLM fallback) produces JSON with per-field confidence
6. JSON saved to `storage/json/`; metadata (upload time, type, version, model used) saved to `storage/metadata/`
7. Embeddings generated from extracted JSON + raw text, indexed in a vector DB
8. Downstream consumers (RAG Q&A, ATS scoring, JD matching, career recs) read only from the storage layer — never touch extraction models directly

## Models

| Model | Role |
|---|---|
| **Donut** | Primary — OCR-free encoder-decoder, fastest path to an end-to-end working pipeline |
| **LayoutLMv3** | Secondary — benchmark/comparison against Donut, needs OCR + bounding boxes first |
| **Prompted VLM** (Qwen2.5-VL or API-based) | Used where no labeled training data exists — zero/few-shot, schema-prompted extraction |

## Datasets

| Dataset | Use |
|---|---|
| **RVL-CDIP** | Document type classification (includes a resume class) |
| **FUNSD / XFUND** | Form-style key-value extraction baseline — used to test transfer to certificates/transcripts, not as a direct fine-tuning solution (domains don't match) |
| **DocVQA** | Document question-answering, for the RAG Q&A feature |
| **Hand-annotated set (20–40 docs)** | No public dataset exists for resume/certificate visual layout extraction — this gap is stated as an explicit finding, and is the justification for prompt-based extraction on these document types |

## Evaluation

Beyond precision/recall/F1:
- Extraction accuracy (overall JSON correctness)
- Exact match (fully correct extraction per document)
- Field-level accuracy (per-field, e.g. name vs. CGPA vs. date)
- Latency per document
- Memory usage

Plus a qualitative **error analysis** across handwritten text, low-resolution scans, rotated/skewed pages, multiple stamps/seals, multiple signatures, embedded tables, and missing/incomplete fields.

## JSON schema design

Every extracted field carries a confidence score, not just a value:

```json
{"name": {"value": "Akshita Sharma", "confidence": 0.98}}
```

- `extraction_model` is a standardized enum (`donut | layoutlmv3 | prompted_vlm`) across all three document schemas
- `confidence` is a float in `0.0–1.0`
- For array fields (education, experience, projects, semester marks), confidence is **per-entry**, not per-sub-field — an intentional v1 simplicity tradeoff
- Documents are versioned per upload (`Resume_v1`, `Resume_v2`, ...) with full history retained

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/documents/upload` | POST | Upload a document, create a new version |
| `/documents/{doc_id}/versions` | GET | List all versions of a document |
| `/documents/{doc_id}/extract` | POST | Run extraction on a given version |
| `/documents/{doc_id}/json` | GET | Fetch extracted JSON |
| `/query` | POST | RAG Q&A over one or more documents |
| `/analysis/ats` | POST | ATS score + explainability (v2) |
| `/analysis/jd-match` | POST | Resume vs. JD match score + gaps (v2) |
| `/analysis/career-recommendations` | GET | Suggested skills/certs/projects (v2) |
| `/analysis/interview-questions` | POST | Interview questions from a resume (v2) |

## Repo structure

```
careerlens/
├── README.md
├── requirements.txt
├── .env.example
├── config.py
├── data/
│   ├── raw/
│   └── annotated/
├── notebooks/
│   ├── 01_dataset_exploration.ipynb
│   ├── 02_donut_baseline.ipynb
│   └── 03_layoutlm_benchmark.ipynb
├── src/
│   ├── schemas.py
│   ├── pdf_to_image.py
│   ├── doc_type_classifier.py
│   ├── donut_extractor.py
│   ├── layoutlm_extractor.py
│   ├── version_manager.py
│   ├── storage.py
│   ├── vector_store.py
│   ├── rag.py
│   ├── ats.py
│   ├── api.py
│   └── utils.py
├── storage/
├── eval/
│   ├── metrics.py
│   └── benchmark.py
└── tests/
```

## Setup

```bash
git clone <repo-url>
cd careerlens
pip install -r requirements.txt
cp .env.example .env  # add HuggingFace token, VLM API key, etc.
```

`pdf2image` requires **poppler** installed at the OS level (not via pip):
```bash
# Linux
apt install poppler-utils
# macOS
brew install poppler
```

## Status

v1 in progress. See the milestone checklist and week-by-week build order in project docs.

## Future work

Additional document types (offer letters, ID cards, research papers, notices), multi-document reasoning, agentic multi-step workflows, multi-language support, incremental learning, mobile scanning support, enterprise deployment considerations.
