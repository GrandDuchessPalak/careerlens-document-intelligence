<<<<<<< HEAD
"""RAG Q&A over extracted JSON + OCR text. Swap `llm_complete` for your LangChain chain if preferred;
the retrieval layer (vector_store.py) is independent of it."""
from typing import List, Optional

import config
from .utils import llm_complete

SYSTEM = ("You answer questions about a student's documents using ONLY the provided context. "
          "If the answer is not in the context, say you could not find it. "
          "Cite sources in the form [doc_id vN].")


def answer(question: str, doc_ids: Optional[List[str]] = None, k: int = config.TOP_K, store=None) -> dict:
    if store is None:
        from .vector_store import VectorStore
        store = VectorStore()
    hits = store.query(question, k=k, doc_ids=doc_ids)
    if not hits:
        return {"answer": "No indexed documents matched. Upload and extract a document first.", "sources": []}
    ctx = "\n".join(f"[{h['metadata']['doc_id']} v{h['metadata']['version']}] {h['text']}" for h in hits)
    text = llm_complete(f"Context:\n{ctx}\n\nQuestion: {question}", system=SYSTEM, max_tokens=800)
    return {"answer": text,
            "sources": [{"doc_id": h["metadata"]["doc_id"], "version": h["metadata"]["version"],
                         "text": h["text"]} for h in hits]}
=======
from __future__ import annotations

import logging
from typing import List, Optional

from pydantic import BaseModel

from config import get_settings
from vector_store import query as vector_query

logger = logging.getLogger(__name__)

RAG_PROMPT_TEMPLATE = """Answer the question using ONLY the context below.
If the context doesn't contain the answer, say you don't know.

Context:
{context}

Question: {question}
Answer:"""


class RAGAnswer(BaseModel):
    answer: str
    sources: List[dict]


class RAGError(RuntimeError):
    pass


def answer_question(question: str, doc_id: Optional[str] = None, top_k: int = 5) -> RAGAnswer:
    hits = vector_query(question, doc_id=doc_id, top_k=top_k)
    if not hits:
        raise RAGError("No relevant context found for this question.")

    context = "\n---\n".join(h["text"] for h in hits)
    prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

    answer_text = _call_llm(prompt)
    return RAGAnswer(answer=answer_text, sources=[h["metadata"] for h in hits])


def _call_llm(prompt: str) -> str:
    settings = get_settings()

    if settings.vlm_provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=settings.vlm_api_key.get_secret_value() if settings.vlm_api_key else None)
        response = client.chat.completions.create(
            model=settings.vlm_model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content

    raise NotImplementedError(f"LLM provider '{settings.vlm_provider}' not wired up for RAG yet.")
>>>>>>> 22298f89189fd0a2a37213efc84616474a0cc990
