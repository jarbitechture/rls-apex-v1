"""GET /cao/{rls_id} returns index.html so the SPA router takes over."""
import pytest


@pytest.mark.asyncio
async def test_cao_path_returns_html(client):
    r = await client.get("/cao/RLS-25-067")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert b"<rls-shell></rls-shell>" in r.content


@pytest.mark.asyncio
async def test_cao_path_with_alphanumeric_rlsid(client):
    r = await client.get("/cao/abc-123_xyz")
    assert r.status_code == 200
