"""Verify 001_baseline creates expected tables."""
import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_baseline_migration_creates_core_tables(db_pool):
    expected = {"rls", "lineage_event", "audit_event", "validation_result", "alembic_version"}
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        actual = {r["tablename"] for r in rows}
    assert expected.issubset(actual), f"missing: {expected - actual}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_lineage_event_unique_constraint(db_pool):
    """`(rls_id, sequence)` must be unique — anchors hash chain integrity."""
    async with db_pool.acquire() as conn:
        # Insert a stub rls row first (FK dependency)
        await conn.execute(
            "INSERT INTO rls (rls_id, classification, status, type, subject, department, contact_name, contact_extension, lineage_head) "
            "VALUES ($1, 'public_record', 'Draft', 'permit_or_zoning', 's', 'd', 'c', '1', $2)",
            "RLS-26-0001", "0" * 64,
        )
        await conn.execute(
            "INSERT INTO lineage_event (rls_id, sequence, prev_hash, this_hash, payload) "
            "VALUES ($1, $2, $3, $4, $5::jsonb)",
            "RLS-26-0001", 1, None, "a" * 64, "{}",
        )
        with pytest.raises(Exception, match="duplicate key"):
            await conn.execute(
                "INSERT INTO lineage_event (rls_id, sequence, prev_hash, this_hash, payload) "
                "VALUES ($1, $2, $3, $4, $5::jsonb)",
                "RLS-26-0001", 1, "a" * 64, "b" * 64, "{}",
            )
