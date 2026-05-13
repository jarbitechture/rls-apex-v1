"""Shared retrieval library — imported by list_rls_precedents and get_policy_snippets."""
from mcp_tools._lib.corpus.embed_client import EmbedClient, EmbeddingUnavailable
from mcp_tools._lib.corpus.retriever import HybridRetriever
from mcp_tools._lib.corpus.types import Hit, SourceType

__all__ = ["Hit", "SourceType", "EmbedClient", "EmbeddingUnavailable", "HybridRetriever"]
