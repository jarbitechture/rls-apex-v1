"""JWT verification for MCP tool inbound auth (spec §4.6).

Per Lock #7 + spec §4.6 common contract: tools verify the gateway's RS256
signature and read actor identity from claims. No X-Apex-Actor-* side
channel.

Tolerance: +/-5s on iat/nbf to handle clock skew between gateway and tool
processes (E2 deferral from spec §15).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

JWT_LEEWAY_SECONDS = 5  # E2: clock-skew tolerance


@dataclass(frozen=True)
class JwtClaims:
    actor_id: str
    actor_role: str
    tenant: str
    rls_id: str | None  # None unless gateway scoped this token to a specific RLS


class JwtRejection(Exception):
    """Token failed verification. Tool returns 401."""


def verify_tool_jwt(
    raw_token: str,
    *,
    expected_audience: str,
    public_key: str,
    issuer: str = "rls-apex-gateway",
) -> JwtClaims:
    """Decode and verify a tool-bound JWT. Returns claims on success.

    Raises JwtRejection on any verification failure.
    """
    try:
        decoded: dict[str, Any] = jwt.decode(
            raw_token,
            public_key,
            algorithms=["RS256"],
            audience=expected_audience,
            issuer=issuer,
            options={"leeway": JWT_LEEWAY_SECONDS},
        )
    except ExpiredSignatureError as exc:
        raise JwtRejection(f"token expired: {exc}") from exc
    except JWTClaimsError as exc:
        if "audience" in str(exc).lower():
            raise JwtRejection(f"audience mismatch: {exc}") from exc
        raise JwtRejection(f"claims error: {exc}") from exc
    except JWTError as exc:
        raise JwtRejection(f"signature/format error: {exc}") from exc

    for required in ("actor_id", "actor_role", "tenant"):
        if required not in decoded or not decoded[required]:
            raise JwtRejection(f"missing required claim: {required}")

    return JwtClaims(
        actor_id=decoded["actor_id"],
        actor_role=decoded["actor_role"],
        tenant=decoded["tenant"],
        rls_id=decoded.get("rls_id"),
    )
