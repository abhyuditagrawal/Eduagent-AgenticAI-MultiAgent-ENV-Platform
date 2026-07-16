import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": "newuser_auth@test.com",
        "password": "securepass123",
        "full_name": "New User",
    })
    # May be 200 or 201 depending on implementation
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "email": "duplicate_auth@test.com",
        "password": "securepass123",
        "full_name": "First User",
    }
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "securepass123",
        "full_name": "Bad Email",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    email = "login_test_auth@test.com"
    await client.post("/api/auth/register", json={
        "email": email,
        "password": "testpass123",
        "full_name": "Login User",
    })
    resp = await client.post("/api/auth/login", json={
        "email": email,
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    email = "wrong_pw_auth@test.com"
    await client.post("/api/auth/register", json={
        "email": email,
        "password": "correctpass",
        "full_name": "Wrong PW",
    })
    resp = await client.post("/api/auth/login", json={
        "email": email,
        "password": "incorrectpass",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_no_token(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_protected_route_invalid_token(client: AsyncClient):
    resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_returns_user(client: AsyncClient, student_token: str):
    resp = await client.get("/api/auth/me", headers=auth_header(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert data["role"] == "student"
