"""Lineage tamper-evidence — the legal anchor (DECISION_LOG Lock #20).

Pure functions, no I/O. Spec 2026-05-18-rls-persistence-genesis-design.md
§5.1 (canonical profile, rules 1-6), §5.2 (link), §5.3 (verify), §7 (the
content-digest idempotency key). This algorithm is normative and
self-specified; it is NOT RFC 8785/JCS. Changing it is a chain-breaking,
chain_version-gated event — never edit in place (Lock #20 reversal cost).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

CHAIN_VERSION = "1"


class CanonicalProfileError(ValueError):
    """Payload violates the §5.1 strict string-only canonical profile."""


def _assert_profile(payload: dict[str, Any]) -> None:
    if payload.get("chain_version") != CHAIN_VERSION:
        raise CanonicalProfileError(
            f"payload must include chain_version={CHAIN_VERSION!r}"
        )
    for k, v in payload.items():
        if not isinstance(k, str):
            raise CanonicalProfileError(f"non-string key: {k!r}")
        if not isinstance(v, str):
            raise CanonicalProfileError(
                f"value for {k!r} is {type(v).__name__}; profile is string-only "
                "(no int/float/bool/None/nested) — flatten or stringify, omit if absent"
            )


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """§5.1: strict string-only, NFC-normalized, sorted keys, compact, UTF-8.

    Normative algorithm — an auditor reproduces it from Lock #20 + this code.
    """
    _assert_profile(payload)
    norm = {k: unicodedata.normalize("NFC", v) for k, v in payload.items()}
    return json.dumps(
        norm, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
