from sqlalchemy import select

from app.core.security import hash_password
from app.database import async_session_factory
from app.models.user import Role, User


async def _login(client, username, password):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_user(username, password, role_name):
    async with async_session_factory() as session:
        role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one()
        session.add(
            User(username=username, password_hash=hash_password(password), role_id=role.id)
        )
        await session.commit()


async def test_inspector_cannot_update_settings(client):
    await _create_user("inspector1", "inspector123", "inspector")
    headers = await _login(client, "inspector1", "inspector123")
    update = await client.put(
        "/api/settings/hammali_rate",
        json={"value": "99"},
        headers=headers,
    )
    assert update.status_code == 403


async def test_inspector_can_read(client):
    await _create_user("inspector2", "inspector123", "inspector")
    headers = await _login(client, "inspector2", "inspector123")
    read = await client.get("/api/settings", headers=headers)
    assert read.status_code == 200


async def test_admin_can_update_settings(client):
    headers = await _login(client, "admin", "admin123")
    update = await client.put(
        "/api/settings/hammali_rate",
        json={"value": "12.05"},
        headers=headers,
    )
    assert update.status_code == 200


async def test_search_requires_auth(client):
    resp = await client.get("/api/v1/search?q=10")
    assert resp.status_code == 401


async def test_search_returns_bills(client):
    headers = await _login(client, "admin", "admin123")
    resp = await client.get("/api/v1/search?q=10", headers=headers)
    assert resp.status_code == 200
    assert "items" in resp.json()
