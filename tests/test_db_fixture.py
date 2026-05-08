"""Verify the Postgres test fixture works."""
import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_db_pool_executes_query(db_pool):
    async with db_pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1
