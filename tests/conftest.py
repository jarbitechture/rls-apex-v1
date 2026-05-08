"""Shared test fixtures."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    """Async HTTP client bound to the gateway ASGI app."""
    from apps.gateway.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


import asyncpg
from pytest_postgresql import factories

# Spin up an ephemeral Postgres for each test session.
postgresql_proc = factories.postgresql_proc(port=None, unixsocketdir="/tmp")
postgresql = factories.postgresql("postgresql_proc")


@pytest.fixture
async def db_pool(postgresql):
    """Async asyncpg pool against the ephemeral test Postgres."""
    dsn = (
        f"postgresql://{postgresql.info.user}:@"
        f"{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()
