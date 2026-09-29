import pytest


async def _login(client, username="admin", password="admin123"):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _commodity_id(client, headers, name):
    resp = await client.get("/api/v1/commodities", headers=headers)
    assert resp.status_code == 200, resp.text
    for item in resp.json()["items"]:
        if item["name"] == name:
            return item["id"]
    raise AssertionError(f"commodity {name} not found")


async def _trader_id(client, headers, name):
    resp = await client.get(f"/api/v1/traders?q={name}", headers=headers)
    assert resp.status_code == 200, resp.text
    for item in resp.json()["items"]:
        if item["name"] == name:
            return item["id"]
    raise AssertionError(f"trader {name} not found")


@pytest.mark.asyncio
async def test_stock_returns_aggregate(client):
    headers = await _login(client)
    resp = await client.get("/api/v1/stock", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    totals = data["totals"]
    assert totals["qty"] == 37400.0
    assert totals["value"] == 1199400.0
    assert totals["commodities"] == 6
    assert totals["rows"] == 10
    assert len(data["rows"]) == 10
    for row in data["rows"]:
        assert "commodity_name" in row
        assert "segment" in row
        assert "qty" in row
        assert "value" in row


@pytest.mark.asyncio
async def test_stock_segment_filter(client):
    headers = await _login(client)
    trader = await client.get("/api/v1/stock?segment=trader", headers=headers)
    assert trader.status_code == 200, trader.text
    trader_rows = trader.json()["rows"]
    assert len(trader_rows) == 6
    assert sum(r["bill_count"] for r in trader_rows) == 8
    assert all(r["segment"] == "trader" for r in trader_rows)

    govt = await client.get("/api/v1/stock?segment=government", headers=headers)
    assert govt.status_code == 200, govt.text
    govt_rows = govt.json()["rows"]
    assert len(govt_rows) == 4
    assert all(r["segment"] == "government" for r in govt_rows)


@pytest.mark.asyncio
async def test_stock_commodity_filter(client):
    headers = await _login(client)
    soybean_id = await _commodity_id(client, headers, "Soybean")
    resp = await client.get(f"/api/v1/stock?commodity_id={soybean_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()["rows"]
    assert len(rows) == 2
    assert all(r["commodity_name"] == "Soybean" for r in rows)


@pytest.mark.asyncio
async def test_stock_search_q(client):
    headers = await _login(client)
    resp = await client.get("/api/v1/stock?q=Wheat", headers=headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()["rows"]
    assert len(rows) == 2
    assert all(r["commodity_name"] == "Wheat" for r in rows)


@pytest.mark.asyncio
async def test_stock_invalid_segment_400(client):
    headers = await _login(client)
    resp = await client.get("/api/v1/stock?segment=bogus", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_stock_analytics(client):
    headers = await _login(client)
    resp = await client.get("/api/v1/stock/analytics?days=30", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["top_commodity"] == "Soybean"
    assert data["total_value"] == 1199400.0
    by_segment = {b["name"]: b for b in data["by_segment"]}
    assert set(by_segment) == {"trader", "government"}
    assert by_segment["trader"]["bills"] == 8
    assert by_segment["government"]["bills"] == 4
    assert data["daily"]
    assert data["daily"] == sorted(data["daily"], key=lambda d: d["date"])
    assert sum(d["qty"] for d in data["daily"]) == 37400.0
    assert sum(d["value"] for d in data["daily"]) == 1199400.0


@pytest.mark.asyncio
async def test_trader_stock_endpoint(client):
    headers = await _login(client)
    trader_id = await _trader_id(client, headers, "Sharma Traders")
    resp = await client.get(f"/api/v1/stock/traders/{trader_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["rows"]
    assert data["totals"]["qty"] == 6700.0
    assert data["totals"]["value"] == 177500.0
    assert all(r["trader_name"] == "Sharma Traders" for r in data["rows"])


@pytest.mark.asyncio
async def test_stock_requires_auth(client):
    resp = await client.get("/api/v1/stock")
    assert resp.status_code == 401
