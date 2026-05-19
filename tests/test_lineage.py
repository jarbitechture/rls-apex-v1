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
