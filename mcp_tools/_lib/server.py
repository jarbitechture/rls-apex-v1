"""Common bootstrap for an MCP tool server.

Each tool's server.py imports build_tool_app(...) and adds its tool definitions.

Provides:
- /health endpoint (via FastMCP `custom_route`) returning `{tool, breakers}`
  per spec §12.4
- A `require_actor()` helper tools call at the top of each `@app.tool` function
  to verify the gateway's RS256 JWT and read actor identity from claims
  (spec §4.6 common contract)
- A `ToolRoiEmitter` instance bound to this tool name

API note (FastMCP 2.3.0): FastMCP exposes `custom_route` for arbitrary HTTP
endpoints and `get_http_request()` for tool-side access to the underlying
Starlette request. There is no `app.middleware()` decorator. JWT enforcement
is therefore per-tool-function rather than middleware-level — every tool
handler must call `require_actor(audience=...)` before doing real work.
This is the contract D2/D3/D4 must follow.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_tools._lib.jwt_verify import JwtClaims, JwtRejection, verify_tool_jwt
from mcp_tools._lib.roi_emit import ToolRoiEmitter


def _load_public_key() -> str:
    """Read the gateway public key from disk, or return a sentinel for tests."""
    public_key_path = os.environ.get(
        "MCP_GATEWAY_PUBLIC_KEY_PATH", "/etc/rls-apex/gateway.pub"
    )
    path = Path(public_key_path)
    if path.exists():
        return path.read_text()
    # In tests, the public key is injected directly into require_actor.
    return ""


def build_tool_app(
    tool_name: str,
    audience: str | None = None,
) -> tuple[FastMCP, ToolRoiEmitter, Callable[..., JwtClaims]]:
    """Construct a FastMCP app, ROI emitter, and `require_actor` helper for a tool.

    Args:
        tool_name: e.g., "validate_rls_structure"
        audience: defaults to f"tool.{tool_name}"

    Returns:
        (app, roi, require_actor) — call require_actor() at the top of each
        @app.tool function to verify the gateway-issued JWT.
    """
    audience = audience or f"tool.{tool_name}"
    public_key = _load_public_key()

    app = FastMCP(tool_name)
    roi = ToolRoiEmitter(tool_name)

    @app.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:  # pragma: no cover - thin shim
        return JSONResponse({"tool": tool_name, "breakers": [roi.breaker_status()]})

    def require_actor(*, override_public_key: str | None = None) -> JwtClaims:
        """Verify the gateway JWT on the current MCP request and return claims.

        Call this at the top of every @app.tool function. Raises JwtRejection
        on any verification failure — the surrounding tool wrapper translates
        that to a 401-equivalent MCP error.

        `override_public_key` is for tests; production paths read from
        MCP_GATEWAY_PUBLIC_KEY_PATH at module init.
        """
        request = get_http_request()
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            raise JwtRejection("missing bearer token")
        token = auth[len("Bearer ") :]
        return verify_tool_jwt(
            token,
            expected_audience=audience,
            public_key=override_public_key or public_key,
        )

    return app, roi, require_actor
