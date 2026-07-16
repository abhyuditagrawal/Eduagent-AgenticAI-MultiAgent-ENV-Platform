import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_list_subjects(client: AsyncClient):
    resp = await client.get("/api/subjects")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_subject_admin(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/subjects",
        json={"code": "TEST_SUBJ", "name": "Test Subject", "description": "A test subject"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "TEST_SUBJ"


@pytest.mark.asyncio
async def test_create_subject_student_forbidden(client: AsyncClient, student_token: str):
    resp = await client.post(
        "/api/subjects",
        json={"code": "NOPE", "name": "Nope", "description": "Should fail"},
        headers=auth_header(student_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_enroll_in_subject(client: AsyncClient, admin_token: str, student_token: str):
    # Create a subject first
    create_resp = await client.post(
        "/api/subjects",
        json={"code": "ENROLL_T", "name": "Enroll Test"},
        headers=auth_header(admin_token),
    )
    subject_id = create_resp.json()["id"]

    # Enroll
    resp = await client.post(
        f"/api/subjects/{subject_id}/enroll",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_double_enrollment(client: AsyncClient, admin_token: str, student_token: str):
    create_resp = await client.post(
        "/api/subjects",
        json={"code": "DBL_ENR", "name": "Double Enroll"},
        headers=auth_header(admin_token),
    )
    subject_id = create_resp.json()["id"]

    await client.post(
        f"/api/subjects/{subject_id}/enroll",
        headers=auth_header(student_token),
    )
    resp = await client.post(
        f"/api/subjects/{subject_id}/enroll",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_enrolled_subjects(client: AsyncClient, student_token: str):
    resp = await client.get(
        "/api/subjects/enrolled",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
