"""TAC-05 — startup guard against external LLM hosts.

The guard refuses to let the gateway boot if LLM_PROVIDER is set to a real
provider AND the corresponding *_BASE_URL points to a host outside the
county-LAN allowlist. No outbound HTTP; pure URL parse + suffix match.

These tests call `assert_llm_endpoint_allowed()` directly with patched env
rather than driving the full FastAPI lifespan — the guard is the unit under
test, not the rest of boot.
"""
from __future__ import annotations

import pytest

from apps.gateway.main import _host_allowed, assert_llm_endpoint_allowed


# ─── Suffix-match unit tests ──────────────────────────────────────


def test_host_allowed_exact_match():
    assert _host_allowed("infer01") is True
    assert _host_allowed("llm01") is True
    assert _host_allowed("localhost") is True
    assert _host_allowed("127.0.0.1") is True
    assert _host_allowed("manatee-civic-ai.internal") is True


def test_host_allowed_suffix_match():
    assert _host_allowed("infer01.county.local") is True
    assert _host_allowed("llm01.bcc.manatee") is True
    assert _host_allowed("infer01.foo.bar") is True


def test_host_allowed_rejects_lookalike_prefix():
    """`xinfer01` must NOT match `infer01` — that's substring, not suffix."""
    assert _host_allowed("xinfer01") is False
    assert _host_allowed("infer01-evil.com") is False
    assert _host_allowed("evil-infer01.com") is False
    assert _host_allowed("notlocalhost") is False


def test_host_allowed_rejects_external():
    assert _host_allowed("api.openai.com") is False
    assert _host_allowed("api.anthropic.com") is False
    assert _host_allowed("generativelanguage.googleapis.com") is False
    assert _host_allowed("") is False


# ─── Full guard tests with env patching ───────────────────────────


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip every env var the guard reads so each test starts from zero."""
    for var in (
        "LLM_PROVIDER",
        "OLLAMA_BASE_URL",
        "SGLANG_BASE_URL",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def test_mock_provider_passes_without_env(monkeypatch):
    """LLM_PROVIDER=mock (the default) must not require any base URL."""
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    # Should not raise.
    assert_llm_endpoint_allowed()


def test_unset_provider_defaults_to_mock(monkeypatch):
    """Missing LLM_PROVIDER is treated as mock and passes."""
    # _clean_env already removed LLM_PROVIDER.
    assert_llm_endpoint_allowed()


def test_ollama_on_internal_host_passes(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://infer01.county.local:11434")
    assert_llm_endpoint_allowed()


def test_ollama_on_localhost_passes(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    assert_llm_endpoint_allowed()


def test_ollama_pointing_at_openai_aborts(monkeypatch):
    """The 'oops, my OPENAI_BASE_URL got copy-pasted' scenario must abort boot."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://api.openai.com/v1")
    with pytest.raises(RuntimeError) as exc:
        assert_llm_endpoint_allowed()
    msg = str(exc.value)
    assert "api.openai.com" in msg
    assert "infer01" in msg  # allowlist mentioned in error
    assert "llm01" in msg


def test_ollama_missing_base_url_aborts(monkeypatch):
    """LLM_PROVIDER=ollama with no OLLAMA_BASE_URL must abort — don't let
    the gateway fall through to whatever the LLM client defaults to."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    # OLLAMA_BASE_URL deliberately unset.
    with pytest.raises(RuntimeError) as exc:
        assert_llm_endpoint_allowed()
    assert "OLLAMA_BASE_URL" in str(exc.value)
