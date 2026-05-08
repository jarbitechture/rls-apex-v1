"""Shared test fixtures."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    """Async HTTP client bound to the gateway ASGI app.

    Overrides current_user so authenticated endpoints work under TestClient
    without requiring DEV_AUTH_BYPASS or a real Entra token. Tests that want
    to exercise the auth gate itself should clear this override.
    """
    from apps.gateway.main import app, current_user

    def _fake_user() -> dict:
        return {
            "upn": "test@local",
            "display_name": "Test User",
            "role": "general-counsel",
            "dept": "DEV",
            "role_band": "professional",
        }

    app.dependency_overrides[current_user] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(current_user, None)


import asyncpg
from pytest_postgresql import factories

# Spin up an ephemeral Postgres for each test session.
postgresql_proc = factories.postgresql_proc(port=None, unixsocketdir="/tmp")
postgresql = factories.postgresql("postgresql_proc")


@pytest.fixture
async def db_pool(postgresql):
    """Async asyncpg pool against the ephemeral test Postgres, with 001_baseline applied."""
    import os
    import subprocess
    import sys
    dsn = (
        f"postgresql://{postgresql.info.user}:@"
        f"{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )
    env = {
        "DB_USER": postgresql.info.user,
        "DB_PASSWORD": "",
        "DB_HOST": postgresql.info.host,
        "DB_PORT": str(postgresql.info.port),
        "DB_NAME": postgresql.info.dbname,
        "PATH": os.environ.get("PATH", ""),
    }
    # Invoke alembic via the same interpreter so it sees pytest's installed deps.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade failed (exit {result.returncode})\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()
