# Synthetic stub opinions — RLS Apex v0.2.1a

18 hand-crafted stub opinions used to test the redaction pipeline (Stream B)
and seed retrieval testing (Stream C) before real opinions are accessible.

## Authoring convention

- Filename: `stub-{matter_type}-{N}.md` where `matter_type ∈ {code_enforcement_litigation, permit_or_zoning, procurement, public_records, general_advisory, other}` and `N ∈ {1, 2, 3}`
- ≥800 words each
- Each MUST contain at minimum (validated by `tests/services/redaction/test_stub_quality.py`):
  - ≥1 SSN pattern: `\d{3}-\d{2}-\d{4}` — use 999-prefix (e.g., `999-99-1234`) to flag synthetic
  - ≥1 phone pattern: `(NNN) NNN-NNNN` or `NNN-NNN-NNNN` — use 555-prefix in the exchange (e.g., `(941) 555-0142`)
  - ≥1 Bates label: `MC-NNNNNN`
  - ≥1 privilege marker: `[ATTORNEY-CLIENT PRIVILEGED]` or `[WORK PRODUCT]` or `[PRIVILEGED]`

## Realism

Stubs should read like Manatee County Attorney opinions in tone + citation
style (LDC §X.Y, Procedure 26-104.001, Ch. 2-26 references, Fla. Stat. cites).
They're test fixtures, NOT real opinions — every name, address, case number,
and SSN must be synthetic. Do not use real Manatee residents or actual ongoing
matters. Synthetic markers used throughout this corpus:

- Phone: `(941) 555-NNNN` (555 exchange is reserved)
- SSN: `999-NN-NNNN` (999-prefix not assigned by SSA)
- Email: `xxx@example.com` (RFC 2606 reserved)
- Address: streets that don't exist (e.g., "Synthetic Lane", "Fixture Drive")

## Purpose

These stubs unblock Stream C retrieval testing immediately while Stream B
governance work (Legal access for the real ~50 opinions) runs in parallel.
They will be ingested into `corpus_chunks` with `source_type="internal_opinion"`
via the redaction pipeline (`services/redaction/`) and removed/replaced once
real opinions land.
