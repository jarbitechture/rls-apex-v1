"""Pool factory creates a working asyncpg pool with documented sizing."""
import pytest

from apps.gateway.db.pool import create_pool, GATEWAY_POOL_SIZE


def test_gateway_pool_size_documented():
    """Sizing is intentional, not magic. W2: 8 max for gateway."""
    assert GATEWAY_POOL_SIZE == (1, 8)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_pool_executes_query(postgresql):
    dsn = f"postgresql://{postgresql.info.user}:@{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    pool = await create_pool(dsn, sizing=(1, 4))
    try:
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT 1") == 1
    finally:
        await pool.close()
