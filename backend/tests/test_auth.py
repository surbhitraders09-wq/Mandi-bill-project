async def test_login_success_and_me(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert me.json()["role"] == "administrator"


async def test_login_wrong_password(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_me_without_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_refresh_flow(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login.json()["refresh_token"]
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": token}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_refresh_rejects_access_token(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    access = login.json()["access_token"]
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": access}
    )
    assert resp.status_code == 401
