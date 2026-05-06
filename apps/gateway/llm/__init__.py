"""Gateway LLM client — multi-provider seam.

Defaults to `mock` (canned text). Flip with one env var:

  LLM_PROVIDER=ollama  + OLLAMA_BASE_URL=http://127.0.0.1:11434  + OLLAMA_MODEL=qwen2.5:3b
  LLM_PROVIDER=sglang  + SGLANG_BASE_URL=http://bcc-ap-infer01:30000  + SGLANG_MODEL=qwen2.5-14b-instruct-fp8
  LLM_PROVIDER=openai  + OPENAI_API_KEY=...  + OPENAI_MODEL=gpt-4o-mini

Auto-detection: if LLM_PROVIDER is unset, the first reachable provider is chosen
(sglang > ollama > openai). If none are configured, falls back to mock — which
streams the caller's `answer_hint` text token-by-token.

Public surface:
    from apps.gateway.llm import stream_completion, provider, status
    async for tok in stream_completion(system, user, citations=..., answer_hint=...):
        ...

Production: SGLang+Qwen2.5-14B-FP8 on bcc-ap-infer01 is the target.
Dev: Ollama+Qwen2.5:3b is the laptop step-up from mock.
"""
from .client import provider, status, stream_completion, LLMConfig  # re-exports

__all__ = ["provider", "status", "stream_completion", "LLMConfig"]
