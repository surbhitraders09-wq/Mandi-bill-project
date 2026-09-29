import pytest


async def _login(client, username="admin", password="admin123"):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_inspector():
    from app.core.security import hash_password
    from app.database import async_session_factory
    from app.models.user import Role, User
    from sqlalchemy import select

    async with async_session_factory() as session:
        role = (await session.execute(select(Role).where(Role.name == "inspector"))).scalar_one()
        exists = (
            await session.execute(select(User).where(User.username == "inspector_md"))
        ).scalar_one_or_none()
        if exists is None:
            session.add(
                User(username="inspector_md", password_hash=hash_password("inspector123"), role_id=role.id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_list_master_data_seeded(client):
    headers = await _login(client, "admin")
    for path in ["/api/v1/villages", "/api/v1/commodities", "/api/v1/farmers", "/api/v1/traders"]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200, (path, resp.text)
        assert resp.json()["items"]


@pytest.mark.asyncio
async def test_farmer_crud_roundtrip(client):
    headers = await _login(client, "admin")
    created = await client.post(
        "/api/v1/farmers",
        json={
            "name": "Test Farmer",
            "aadhaar": "999999999999",
            "mobile": "9000000000",
            "land_area": 1.5,
            "bank_name": "Test Bank",
            "account_number": "12345",
            "ifsc_code": "TEST0000001",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    farmer = created.json()
    assert farmer["name"] == "Test Farmer"

    got = await client.get(f"/api/v1/farmers/{farmer['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["aadhaar"] == "999999999999"

    updated = await client.put(
        f"/api/v1/farmers/{farmer['id']}",
        json={"mobile": "9111111111"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["mobile"] == "9111111111"

    audit = await client.get("/api/v1/audit?limit=20", headers=headers)
    assert audit.status_code == 200
    assert any("AUDIT CREATE farmer" in item["message"] for item in audit.json()["items"])
    assert any("AUDIT UPDATE farmer" in item["message"] for item in audit.json()["items"])

    deleted = await client.delete(f"/api/v1/farmers/{farmer['id']}", headers=headers)
    assert deleted.status_code == 204
    gone = await client.get(f"/api/v1/farmers/{farmer['id']}", headers=headers)
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_trader_crud_roundtrip(client):
    headers = await _login(client, "admin")
    created = await client.post(
        "/api/v1/traders",
        json={
            "name": "Test Trader",
            "gstin": "99ZZZZZ0000Z1Z9",
            "pan": "ZZZZZ0000Z",
            "license_no": "TEST-LIC-001",
            "mobile": "9222222222",
            "commission_rate": 2.0,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    trader = created.json()
    assert trader["commission_rate"] == 2.0

    got = await client.get(f"/api/v1/traders/{trader['id']}", headers=headers)
    assert got.status_code == 200

    deleted = await client.delete(f"/api/v1/traders/{trader['id']}", headers=headers)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_duplicate_aadhaar_rejected(client):
    headers = await _login(client, "admin")
    # 999999999998 is fresh; second insert of same aadhaar should fail
    payload = {"name": "Dup Farmer", "aadhaar": "888888888888", "mobile": "9333333333"}
    first = await client.post("/api/v1/farmers", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    second = await client.post("/api/v1/farmers", json=payload, headers=headers)
    assert second.status_code in (409, 422)


@pytest.mark.asyncio
async def test_inspector_cannot_write_master_data(client):
    await _create_inspector()
    resp = await client.post("/api/v1/auth/login", json={"username": "inspector_md", "password": "inspector123"})
    assert resp.status_code == 200, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    created = await client.post(
        "/api/v1/farmers",
        json={"name": "Blocked Farmer", "aadhaar": "777777777777"},
        headers=headers,
    )
    assert created.status_code == 403

    listed = await client.get("/api/v1/farmers", headers=headers)
    assert listed.status_code == 200


@pytest.mark.asyncio
async def test_search_finds_farmer(client):
    headers = await _login(client, "admin")
    resp = await client.get("/api/v1/search?q=Ram%20Singh", headers=headers)
    assert resp.status_code == 200
    hits = resp.json()["items"]
    assert any(h["type"] == "farmer" and h["title"] == "Ram Singh Patel" for h in hits)
