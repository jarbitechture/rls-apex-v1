"""Corpus retrieval — single contract, two implementations.

Today (DEV_MODE):  in-process BM25 over PDFs/CSV in corpus/raw/.
Tomorrow (prod):    BM25 + LightRAG + Contextual Retrieval + Qwen3-Embedding
                    + pgvector on bcc-db-llm01. Same retrieve() signature.

Public surface:
    from apps.gateway.retrieval import load, retrieve, manifest
    load()                        # warm the in-process index (idempotent)
    retrieve(q, k=12, classification_filter=None) -> list[Citation]
    manifest() -> dict             # ingested-document metadata
"""
from .retrieve import load, retrieve, manifest, Citation  # re-exports

__all__ = ["load", "retrieve", "manifest", "Citation"]
