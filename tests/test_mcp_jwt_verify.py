"""Tools verify the gateway's RS256 JWT and read actor identity from claims (spec §4.6)."""
import time
from pathlib import Path

import pytest
from jose import jwt

from mcp_tools._lib.jwt_verify import (
    JwtClaims,
    JwtRejection,
    verify_tool_jwt,
)

FIXTURES = Path(__file__).parent / "fixtures"
TEST_PRIVATE_KEY = (FIXTURES / "test_rsa.pem").read_text()
TEST_PUBLIC_KEY = (FIXTURES / "test_rsa.pub").read_text()


def _make_token(claims: dict) -> str:
    return jwt.encode(claims, TEST_PRIVATE_KEY, algorithm="RS256")


def test_valid_token_returns_claims():
    now = int(time.time())
    raw = _make_token({
        "iss": "rls-apex-gateway",
        "aud": "tool.classify_matter",
        "iat": now,
        "exp": now + 60,
        "actor_id": "ejarbe@mymanatee.org",
        "actor_role": "attorney",
        "tenant": "manatee",
    })
    claims = verify_tool_jwt(raw, expected_audience="tool.classify_matter", public_key=TEST_PUBLIC_KEY)
    assert claims.actor_id == "ejarbe@mymanatee.org"
    assert claims.actor_role == "attorney"


def test_wrong_audience_rejected():
    now = int(time.time())
    raw = _make_token({
        "iss": "rls-apex-gateway",
        "aud": "tool.OTHER",
        "iat": now,
        "exp": now + 60,
        "actor_id": "ejarbe@mymanatee.org",
        "actor_role": "attorney",
        "tenant": "manatee",
    })
    with pytest.raises(JwtRejection, match="audience"):
        verify_tool_jwt(raw, expected_audience="tool.classify_matter", public_key=TEST_PUBLIC_KEY)


def test_expired_token_rejected():
    now = int(time.time())
    raw = _make_token({
        "iss": "rls-apex-gateway",
        "aud": "tool.classify_matter",
        "iat": now - 120,
        "exp": now - 60,
        "actor_id": "x", "actor_role": "y", "tenant": "z",
    })
    with pytest.raises(JwtRejection, match="expired"):
        verify_tool_jwt(raw, expected_audience="tool.classify_matter", public_key=TEST_PUBLIC_KEY)


def test_clock_skew_5_seconds_tolerated():
    """E2 deferral — JWTs accepted +/-5s from nbf.

    Uses nbf (not-before) since python-jose enforces nbf-with-leeway by default;
    iat is informational only. With nbf=now+4 and leeway=5, the token must be
    accepted; with leeway=0 the same token would raise.
    """
    now = int(time.time())
    raw = _make_token({
        "iss": "rls-apex-gateway",
        "aud": "tool.classify_matter",
        "iat": now,
        "nbf": now + 4,  # not-valid-yet by 4s — must succeed under 5s leeway
        "exp": now + 60,
        "actor_id": "x", "actor_role": "y", "tenant": "z",
    })
    claims = verify_tool_jwt(raw, expected_audience="tool.classify_matter", public_key=TEST_PUBLIC_KEY)
    assert claims.actor_id == "x"


def test_missing_required_claim_rejected():
    now = int(time.time())
    raw = _make_token({
        "iss": "rls-apex-gateway",
        "aud": "tool.classify_matter",
        "iat": now,
        "exp": now + 60,
        # Missing actor_id, actor_role, tenant
    })
    with pytest.raises(JwtRejection, match="missing"):
        verify_tool_jwt(raw, expected_audience="tool.classify_matter", public_key=TEST_PUBLIC_KEY)
