"""LLM client — provider selector + provider implementations.

Every code path that streams tokens to the SSE channel goes through
`stream_completion()`. Today the default provider is `mock` (canned
text from `answer_hint`). Tomorrow the user flips LLM_PROVIDER and the
SSE shape stays identical.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


# ─── Config from env ──────────────────────────────────────────────

@dataclass
class LLMConfig:
    # Default is `mock` — every real provider must be opted into explicitly.
    # Set LLM_PROVIDER=auto to enable auto-discovery (sglang > ollama > openai),
    # or LLM_PROVIDER=ollama|sglang|openai to pick one. This avoids any
    # ambient OPENAI_API_KEY in the user's shell silently wiring the gateway
    # to a paid endpoint.
    provider:           str = field(default_factory=lambda: os.environ.get("LLM_PROVIDER", "mock"))

    ollama_base_url:    str = field(default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    ollama_model:       str = field(default_factory=lambda: os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"))

    sglang_base_url:    Optional[str] = field(default_factory=lambda: os.environ.get("SGLANG_BASE_URL"))
    sglang_model:       str = field(default_factory=lambda: os.environ.get("SGLANG_MODEL", "qwen2.5-14b-instruct-fp8"))

    openai_api_key:     Optional[str] = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY"))
    openai_base_url:    str = field(default_factory=lambda: os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_model:       str = field(default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))

    max_tokens:         int = field(default_factory=lambda: int(os.environ.get("LLM_MAX_TOKENS", "512")))
    temperature:        float = field(default_factory=lambda: float(os.environ.get("LLM_TEMPERATURE", "0.2")))
    request_timeout_s:  float = field(default_factory=lambda: float(os.environ.get("LLM_REQUEST_TIMEOUT", "30")))

    def configured_providers(self) -> list[str]:
        out = []
        if self.sglang_base_url: out.append("sglang")
        if self._port_open(self.ollama_base_url): out.append("ollama")
        if self.openai_api_key: out.append("openai")
        return out

    def selected(self) -> str:
        # Explicit override wins. 'auto' enables discovery. Anything else
        # (including the default 'mock') is honored as-is.
        if self.provider == "auto":
            configured = self.configured_providers()
            return configured[0] if configured else "mock"
        return self.provider or "mock"

    @staticmethod
    def _port_open(url: str, timeout_s: float = 0.4) -> bool:
        if not url: return False
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            host = p.hostname or "127.0.0.1"
            port = p.port or (443 if p.scheme == "https" else 80)
            with socket.create_connection((host, port), timeout=timeout_s):
                return True
        except Exception:  # noqa: BLE001
            return False


_cfg = LLMConfig()


def provider() -> str:
    """Return the currently selected provider string."""
    return _cfg.selected()


def status() -> dict:
    """Health snapshot — for /api/health/llm."""
    sel = _cfg.selected()
    return {
        "provider":             sel,
        "configured":           _cfg.configured_providers(),
        "model": {
            "ollama":   _cfg.ollama_model,
            "sglang":   _cfg.sglang_model,
            "openai":   _cfg.openai_model,
        }.get(sel, "—"),
        "endpoints": {
            "ollama":   _cfg.ollama_base_url,
            "sglang":   _cfg.sglang_base_url or "(unset)",
            "openai":   _cfg.openai_base_url,
        },
        "active":   sel != "mock",
    }


# ─── Prompt assembly ──────────────────────────────────────────────

_SYSTEM_DEFAULT = (
    "You are an RLS legal-services assistant for Manatee County BCC. "
    "Answer in plain English, cite supporting sources by id (e.g. RLS-25-0114), "
    "and never invent statutes or opinions. If the supplied context is "
    "insufficient, say so plainly. Do not provide legal advice."
)


def _format_context(citations: Optional[list[dict]]) -> str:
    if not citations:
        return ""
    lines = []
    for c in citations[:6]:
        cid = c.get("id") or c.get("source") or "—"
        pin = c.get("pinpoint") or ""
        excerpt = (c.get("excerpt") or "").strip().replace("\n", " ")
        lines.append(f"[{cid} · {pin}] {excerpt}")
    return "CONTEXT:\n" + "\n".join(lines) + "\n\n"


# ─── Public stream_completion ─────────────────────────────────────

async def stream_completion(
    system: Optional[str] = None,
    user: str = "",
    citations: Optional[list[dict]] = None,
    answer_hint: str = "",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> AsyncIterator[str]:
    """Yield text chunks. The mock provider streams `answer_hint` verbatim;
    real providers stream the model's tokens. Either way the SSE caller
    treats each yielded string as a `token` event payload."""
    sel = _cfg.selected()
    sys_prompt = system or _SYSTEM_DEFAULT
    ctx = _format_context(citations)
    final_user = ctx + f"QUESTION: {user.strip()}" if user.strip() else (ctx + "Provide a brief grounded summary.")

    if sel == "mock":
        async for tok in _mock_stream(answer_hint or "—"):
            yield tok
        return

    mt = max_tokens or _cfg.max_tokens
    temp = temperature if temperature is not None else _cfg.temperature

    try:
        if sel == "ollama":
            async for tok in _ollama_stream(sys_prompt, final_user, mt, temp):
                yield tok
        elif sel == "sglang":
            async for tok in _openai_compat_stream(_cfg.sglang_base_url, _cfg.sglang_model,
                                                    sys_prompt, final_user, mt, temp,
                                                    api_key=None):
                yield tok
        elif sel == "openai":
            async for tok in _openai_compat_stream(_cfg.openai_base_url, _cfg.openai_model,
                                                    sys_prompt, final_user, mt, temp,
                                                    api_key=_cfg.openai_api_key):
                yield tok
        else:
            async for tok in _mock_stream(answer_hint or "(unknown provider)"):
                yield tok
    except Exception as e:  # noqa: BLE001
        # Provider failed mid-stream — fall through to mock so the SSE
        # connection still completes a valid response.
        async for tok in _mock_stream(answer_hint or f"(LLM error: {e})"):
            yield tok


# ─── Provider implementations ─────────────────────────────────────

async def _mock_stream(answer_hint: str) -> AsyncIterator[str]:
    for word in answer_hint.split(" "):
        yield word + " "
        await asyncio.sleep(0.022)


async def _ollama_stream(system: str, user: str, max_tokens: int, temperature: float) -> AsyncIterator[str]:
    """Native Ollama /api/chat with stream=true."""
    import httpx
    body = {
        "model": _cfg.ollama_model,
        "stream": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }
    timeout = httpx.Timeout(_cfg.request_timeout_s, connect=5)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{_cfg.ollama_base_url}/api/chat",
                                  json=body) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("done"):
                    break
                tok = (msg.get("message") or {}).get("content")
                if tok:
                    yield tok


async def _openai_compat_stream(
    base_url: str, model: str, system: str, user: str,
    max_tokens: int, temperature: float, api_key: Optional[str],
) -> AsyncIterator[str]:
    """OpenAI-style /v1/chat/completions with stream=true. Used by both
    SGLang (loopback) and OpenAI (api.openai.com)."""
    import httpx
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }
    timeout = httpx.Timeout(_cfg.request_timeout_s, connect=5)
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        url = f"{base}/v1/chat/completions"
    else:
        url = f"{base}/chat/completions"
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=body, headers=headers) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        msg = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    delta = (msg.get("choices") or [{}])[0].get("delta") or {}
                    tok = delta.get("content")
                    if tok:
                        yield tok
