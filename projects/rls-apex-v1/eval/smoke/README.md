# Smoke eval — DO NOT OPTIMIZE AGAINST

> **Read this before touching `smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl`.**

## What it is

20 cases that prove the **plumbing** works end-to-end:
- Retrieval returns *something* (not empty, not error).
- Graph queries parse and return rows.
- Ontology validates a known-good payload and rejects a known-bad one.
- Lineage stamps generate hashes and chain.
- ROI sidecar accepts events.
- Guardrails fire on the obvious cases.
- Auth, breakers, classification, skills surface — all the structural contracts.

## What it isn't

A quality signal. Specifically:
- The "expected" outputs are **structural shapes**, not content correctness.
- A run that passes all 20 cases tells you the pipeline is alive. It tells you **nothing** about retrieval relevance, citation accuracy, or generation quality.
- The corpus seeded for these tests is intentionally tiny and synthetic.

## Why the file is named like that

Because someone — possibly future-you, possibly an over-eager teammate — will look at "20/20 passing on the smoke set" and infer this is a quality benchmark. The filename is the first line of defense. The README is the second.

## When the real evals come online

GEPA compile (week 5–6) gates on:
- `eval/datasets/rls-v1/` — 50–100 historic RLS opinions, redacted, attorney-graded.
- `eval/promptfoo/` — prompt regression in CI.
- `eval/inspect-ai/` — full agent traces with tool-call grading.

`smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl` stays in CI as a 60-second pre-flight, but it never feeds an optimizer and never appears on a quality report.

## How CI uses this file

```bash
# .github/workflows/ci.yml
- name: Smoke eval (plumbing only)
  run: |
    uv run python -m eval.smoke.run \
      --input eval/smoke/smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl \
      --max-duration 60s
  # If this fails, the PR cannot merge. If it passes, that means
  # nothing about output quality. See README.md.
```
