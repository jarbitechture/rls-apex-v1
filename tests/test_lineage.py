import pytest
from apps.gateway.db.lineage import canonical_bytes, CanonicalProfileError


def test_canonical_bytes_is_sorted_compact_utf8():
    out = canonical_bytes({"b": "2", "a": "1", "chain_version": "1"})
    assert out == b'{"a":"1","b":"2","chain_version":"1"}'
    assert isinstance(out, bytes)


def test_canonical_bytes_nfc_normalizes_string_values():
    nfd = {"k": "é", "chain_version": "1"}   # e + combining acute (NFD)
    nfc = {"k": "é", "chain_version": "1"}      # precomposed é (NFC)
    assert canonical_bytes(nfd) == canonical_bytes(nfc)


def test_canonical_bytes_rejects_non_string_and_nested():
    for bad in ({"a": 1}, {"a": 1.0}, {"a": True}, {"a": None}, {"a": {"x": "1"}}, {"a": ["1"]}):
        with pytest.raises(CanonicalProfileError):
            canonical_bytes({**bad, "chain_version": "1"})


def test_canonical_bytes_requires_chain_version():
    with pytest.raises(CanonicalProfileError):
        canonical_bytes({"a": "1"})


def test_canonical_bytes_escapes_control_chars_no_raw_0x1f():
    out = canonical_bytes({"a": "x\x1fy", "chain_version": "1"})
    assert b"\x1f" not in out
    assert b"\\u001f" in out


# append to tests/test_lineage.py
from apps.gateway.db.lineage import compute_link
import hashlib


def test_compute_link_genesis_known_answer():
    payload = {"chain_version": "1", "rls_id": "RLS-26-0001"}
    expected = hashlib.sha256(
        b"GENESIS" + b"\x1f" + b"1" + b"\x1f"
        + b'{"chain_version":"1","rls_id":"RLS-26-0001"}'
    ).hexdigest()
    got = compute_link(None, 1, payload)
    assert got == expected
    assert len(got) == 64 and got == got.lower()


def test_compute_link_non_genesis_uses_prev_hash():
    prev = "a" * 64
    payload = {"chain_version": "1", "x": "y"}
    expected = hashlib.sha256(
        prev.encode("ascii") + b"\x1f" + b"2" + b"\x1f"
        + b'{"chain_version":"1","x":"y"}'
    ).hexdigest()
    assert compute_link(prev, 2, payload) == expected


# append to tests/test_lineage.py
from apps.gateway.db.lineage import verify_chain
from dataclasses import dataclass


@dataclass
class _Ev:
    sequence: int
    prev_hash: str | None
    this_hash: str
    payload: dict


def _mk(seq, prev):
    p = {"chain_version": "1", "n": str(seq)}
    return _Ev(seq, prev, compute_link(prev, seq, p), p)


def test_verify_chain_accepts_valid_chain():
    g = _mk(1, None)
    e2 = _mk(2, g.this_hash)
    assert verify_chain([g, e2]) is True


def test_verify_chain_rejects_tamper_reorder_and_missing_genesis():
    g = _mk(1, None)
    e2 = _mk(2, g.this_hash)
    tampered = _Ev(2, g.this_hash, e2.this_hash, {"chain_version": "1", "n": "X"})
    assert verify_chain([g, tampered]) is False           # payload tampered
    assert verify_chain([e2, g]) is False                  # reordered
    assert verify_chain([_mk(2, g.this_hash)]) is False    # no genesis (seq!=1)
    broken = _Ev(2, "f" * 64, e2.this_hash, e2.payload)
    assert verify_chain([g, broken]) is False              # broken prev link


# append to tests/test_lineage.py
from apps.gateway.db.lineage import content_idempotency_key


def test_idem_key_is_stable_for_same_content_order_independent():
    a = {"subject": "Lease X", "department": "Legal", "legal_question": "Q?"}
    b = {"legal_question": "Q?", "department": "Legal", "subject": "Lease X"}
    assert content_idempotency_key(a) == content_idempotency_key(b)
    assert len(content_idempotency_key(a)) == 64


def test_idem_key_changes_on_material_edit():
    a = {"subject": "Lease X", "department": "Legal"}
    b = {"subject": "Lease Y", "department": "Legal"}
    assert content_idempotency_key(a) != content_idempotency_key(b)
