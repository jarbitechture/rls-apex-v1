"""asyncpg connection pool factory.

W2 sizing (spec §15):
- Gateway pool: (min=1, max=8). Holds connections for /api/intake, /api/validate,
  /api/health/breakers, plus the audit-write path inside update_rls_status.
- MCP tool pool: (min=1, max=2). Each of the 12 RLS-domain tools runs as a
  separate process with its own pool — bounded so the aggregate stays
  under bcc-db-llm01's max_connections=100 setting.
- Total target: 1*8 + 12*2 = 32 connections under load. Headroom for
  alembic, monitoring, and ad-hoc queries.

Re-evaluate at v0.2.1 if connection pressure shows up. PgBouncer is NOT
introduced in v0.2.0a.
"""
from __future__ import annotations
import asyncpg

GATEWAY_POOL_SIZE: tuple[int, int] = (1, 8)
MCP_TOOL_POOL_SIZE: tuple[int, int] = (1, 2)


async def create_pool(dsn: str, sizing: tuple[int, int] = GATEWAY_POOL_SIZE) -> asyncpg.Pool:
    """Create an asyncpg pool. Sizing is (min, max).

    Raises asyncpg.PostgresError on connection failure — let the lifespan
    surface this as a startup failure, don't swallow it.
    """
    min_size, max_size = sizing
    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        timeout=10.0,         # statement timeout, seconds
        command_timeout=5.0,  # individual query timeout
    )
    return pool


async def healthcheck(pool: asyncpg.Pool) -> dict:
    """Returns a serializable health dict for /readyz consumption."""
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"db": "ok", "pool_size_max": pool.get_max_size(), "pool_size_used": pool.get_size()}
    except Exception as exc:
        return {"db": "error", "error": str(exc)}
