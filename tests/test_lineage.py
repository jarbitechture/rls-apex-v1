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
