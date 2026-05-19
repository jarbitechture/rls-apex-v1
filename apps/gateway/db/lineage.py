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


# append to apps/gateway/db/lineage.py
def compute_link(prev_hash: str | None, sequence: int, payload: dict[str, Any]) -> str:
    """§5.2 link. Genesis = prev_hash None → literal b"GENESIS" sentinel.

    sha256( (prev_hash or "GENESIS").ascii + 0x1F + str(seq).ascii + 0x1F
            + canonical_bytes(payload) ).hexdigest()  — lowercase 64-hex.
    """
    head = (prev_hash or "GENESIS").encode("ascii")
    return hashlib.sha256(
        head
        + b"\x1f"
        + str(sequence).encode("ascii")
        + b"\x1f"
        + canonical_bytes(payload)
    ).hexdigest()


# append to apps/gateway/db/lineage.py
def verify_chain(events: list) -> bool:
    """§5.3: ordered events for one rls_id. Returns False on any failure.

    Each event needs attributes: sequence:int, prev_hash:str|None,
    this_hash:str, payload:dict.
    """
    if not events:
        return False
    for i, ev in enumerate(events):
        expected_seq = i + 1
        if ev.sequence != expected_seq:
            return False
        prev = None if i == 0 else events[i - 1].this_hash
        if ev.prev_hash != prev:
            return False
        if compute_link(ev.prev_hash, ev.sequence, ev.payload) != ev.this_hash:
            return False
    return True


# append to apps/gateway/db/lineage.py
def content_idempotency_key(rls_payload: dict[str, Any]) -> str:
    """§7(b): deterministic digest of the submitted draft content.

    Stringifies every value (the §5.1 profile is string-only), then hashes
    the canonical bytes. Content-stable by construction — same draft yields
    the same key across refresh / new session / lost-response retry, with
    no server state. The server treats this as OPAQUE (it never recomputes
    or trusts it; UNIQUE(idempotency_key) is the sole enforcement).
    """
    flat = {
        k: ("" if v is None else v if isinstance(v, str) else json.dumps(
            v, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        for k, v in rls_payload.items()
    }
    flat["chain_version"] = CHAIN_VERSION
    return hashlib.sha256(canonical_bytes(flat)).hexdigest()
