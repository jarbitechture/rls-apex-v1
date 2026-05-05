# `smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl`

## What this file is

A 20-case (eventually) **plumbing test**. It proves the chain compiles, the
tools dispatch, lineage stamps, and ROI events fire. It does **not** measure
quality. Scores from this file are not, and never will be, a quality signal.

## What this file is NOT

- A metric for prompt iteration.
- A training set for DSPy or GEPA.
- A regression suite for retrieval relevance.
- A gate for stakeholder demos.

If you find yourself wanting any of those, you want a different file.
Real quality signals come from:

| Signal type | Lives in |
|---|---|
| Prompt regression | `eval/promptfoo/` |
| Agent-trace correctness / safety | `eval/inspect-ai/` |
| Attorney-redlined GEPA training | `eval/datasets/rls-v1/redlines/` (week 5–6) |

## Why the alarming filename

Because someone — including a future version of the person who wrote this
note — will see "eval" in the path, see passing scores, and assume the
pipeline is working *well*. The filename is the load-bearing comment.

## What the warning record at line 1 does

Tools that consume JSONL line-by-line will surface the warning when they
read the file. `promptfoo` ignores records with `_warning` keys.

## When to update this file

Only when the **plumbing** changes — a new tool added to the dispatch
path, a new event type in lineage, etc. Adding cases to chase quality is
the failure mode this filename is preventing.
