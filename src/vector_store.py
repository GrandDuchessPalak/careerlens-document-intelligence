from __future__ import annotations

import logging
from typing import List, Optional

import chromadb
from chromadb.utils import embedding_functions

from config import get_settings

logger = logging.getLogger(__name__)

_client = None
_collection = None


class VectorStoreError(RuntimeError):
    pass


def _get_collection():
    global _client, _collection
    if _collection is None:
        settings = get_settings()
        _client = chromadb.PersistentClient(path=settings.vector_store_dir)
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = _client.get_or_create_collection(
            name="careerlens_docs", embedding_function=embed_fn
        )
    return _collection


def index_document(doc_id: str, version: str, text: str, metadata: Optional[dict] = None) -> None:
    """Chunks + embeds a document's extracted text and stores it under doc_id/version."""
    if not text.strip():
        raise VectorStoreError(f"No text to index for {doc_id}/{version}")

    collection = _get_collection()
    chunks = _chunk_text(text)
    ids = [f"{doc_id}:{version}:{i}" for i in range(len(chunks))]
    metas = [{"doc_id": doc_id, "version": version, **(metadata or {})} for _ in chunks]

    collection.add(ids=ids, documents=chunks, metadatas=metas)


def query(question: str, doc_id: Optional[str] = None, top_k: int = 5) -> List[dict]:
    collection = _get_collection()
    where = {"doc_id": doc_id} if doc_id else None

    results = collection.query(query_texts=[question], n_results=top_k, where=where)
    hits = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        hits.append({"text": doc, "metadata": meta, "distance": dist})
    return hits


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks