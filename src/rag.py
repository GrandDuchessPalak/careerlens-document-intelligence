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
