import pytest


@pytest.mark.asyncio
async def test_id_counter_table_exists_and_constrained(db_pool):
    async with db_pool.acquire() as c:
        cols = await c.fetch(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns WHERE table_name='id_counter' "
            "ORDER BY ordinal_position"
        )
    by = {r["column_name"]: r for r in cols}
    assert set(by) == {"year", "next_seq"}
    assert by["year"]["data_type"] == "integer"
    assert by["next_seq"]["is_nullable"] == "NO"
    async with db_pool.acquire() as c:
        await c.execute("INSERT INTO id_counter (year, next_seq) VALUES (2026, 1)")
        with pytest.raises(Exception):
            await c.execute("INSERT INTO id_counter (year, next_seq) VALUES (2026, 9)")
        with pytest.raises(Exception):
            await c.execute("INSERT INTO id_counter (year, next_seq) VALUES (2027, 0)")
