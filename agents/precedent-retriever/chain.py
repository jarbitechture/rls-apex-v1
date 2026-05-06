"""
PrecedentRetriever — DSPy chain (uncompiled in v0.1.0 per D-009).

Pipeline:

  question  ──▶  classify  ──▶  retrieve.hybrid  ──▶  policy_graph.cited_by
                                       │                       │
                                       ▼                       ▼
                                    citations  ◀──  rank  ◀──  graph hits
                                       │
                                       ▼
                                    answer (with inline citations)
                                       │
                                       ▼
                                    guardrails (no-advice, citations≥1, lineage stamped)

Compiled artifact lands at agents/precedent-retriever/compiled/v1.json
in week 5–6, after attorney redlines exist.
"""

from __future__ import annotations

import dspy

# ─── Signatures ───────────────────────────────────────────────────


class ClassifyQuery(dspy.Signature):
    """Decide the retrieval shape for a legal question.

    `kind` drives whether we hit pgvector (semantic), AGE (graph), or both.
    """

    question = dspy.InputField()
    kind = dspy.OutputField(desc="one of: factual, citation_lookup, scope_check, comparison")
    rationale = dspy.OutputField(desc="≤ 1 sentence; never legal advice")


class RankCitations(dspy.Signature):
    """Rank candidate Citation rows by relevance to the question.
    Output is order-only; no score values surface to the user."""

    question = dspy.InputField()
    candidates = dspy.InputField(desc="list of Citation dicts: id, source_kind, pinpoint, excerpt")
    ranked = dspy.OutputField(desc="list of citation ids in priority order")


class ComposeAnswer(dspy.Signature):
    """Compose the user-facing answer with inline citations.

    Guardrails (enforced post-hoc, not by the LLM):
      • Must reference at least one Citation by id
      • Must not contain phrases that read as legal advice
        (rejected by the no-advice classifier in the gateway)
    """

    question = dspy.InputField()
    citations = dspy.InputField()
    answer = dspy.OutputField()


# ─── Module ───────────────────────────────────────────────────────


class PrecedentRetriever(dspy.Module):
    def __init__(self, retrieve_tool, graph_tool):
        super().__init__()
        self.classify = dspy.Predict(ClassifyQuery)
        self.rank = dspy.Predict(RankCitations)
        self.compose = dspy.Predict(ComposeAnswer)
        self.retrieve_tool = retrieve_tool   # MCP client wrapper
        self.graph_tool = graph_tool         # MCP client wrapper

    def forward(self, question: str, matter_id: str | None = None):
        kind = self.classify(question=question)

        # Hybrid retrieval — vector + graph in parallel where possible.
        vector_hits = self.retrieve_tool.hybrid(
            q=question, k=12,
            classification_filter=["public_record", "internal"],
        )

        graph_hits = []
        if kind.kind in ("citation_lookup", "scope_check"):
            graph_hits = self.graph_tool.find_statutes_for_question(question)

        candidates = _merge(vector_hits, graph_hits)
        ranked = self.rank(question=question, candidates=candidates).ranked

        top_citations = [c for c in candidates if c["id"] in ranked[:5]]
        answer = self.compose(question=question, citations=top_citations).answer

        return dspy.Prediction(
            answer=answer,
            citations=top_citations,
            kind=kind.kind,
        )


def _merge(vector_hits, graph_hits):
    """Dedupe by Citation.id; preserve provenance (vector vs graph)."""
    seen = {}
    for h in vector_hits + graph_hits:
        seen.setdefault(h["id"], h)
    return list(seen.values())
