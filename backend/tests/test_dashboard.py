import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_mastery_endpoint_structure(
    client: AsyncClient, admin_token: str, student_token: str
):
    # Create and enroll in a subject
    create_resp = await client.post(
        "/api/subjects",
        json={"code": "DASH_M", "name": "Dashboard Mastery"},
        headers=auth_header(admin_token),
    )
    subject_id = create_resp.json()["id"]
    await client.post(
        f"/api/subjects/{subject_id}/enroll",
        headers=auth_header(student_token),
    )

    resp = await client.get(
        f"/api/dashboard/mastery?subject_id={subject_id}",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "subject" in data
    assert "overall_score" in data
    assert "chapters" in data


@pytest.mark.asyncio
async def test_weak_points_endpoint(
    client: AsyncClient, admin_token: str, student_token: str
):
    create_resp = await client.post(
        "/api/subjects",
        json={"code": "DASH_W", "name": "Dashboard Weak"},
        headers=auth_header(admin_token),
    )
    subject_id = create_resp.json()["id"]
    await client.post(
        f"/api/subjects/{subject_id}/enroll",
        headers=auth_header(student_token),
    )

    resp = await client.get(
        f"/api/dashboard/weak-points?subject_id={subject_id}",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "weak_concepts" in data
    assert "total_weak" in data
    assert "total_concepts" in data


@pytest.mark.asyncio
async def test_exam_readiness_endpoint(
    client: AsyncClient, admin_token: str, student_token: str
):
    create_resp = await client.post(
        "/api/subjects",
        json={"code": "DASH_E", "name": "Dashboard Exam"},
        headers=auth_header(admin_token),
    )
    subject_id = create_resp.json()["id"]
    await client.post(
        f"/api/subjects/{subject_id}/enroll",
        headers=auth_header(student_token),
    )

    resp = await client.get(
        f"/api/dashboard/exam-readiness?subject_id={subject_id}",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_readiness" in data
    assert "readiness_label" in data
    assert "by_difficulty" in data


@pytest.mark.asyncio
async def test_activity_endpoint(client: AsyncClient, student_token: str):
    resp = await client.get(
        "/api/dashboard/activity?days=30",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "daily_activity" in data
    assert "streak" in data
    assert "totals" in data


@pytest.mark.asyncio
async def test_concept_graph_endpoint(
    client: AsyncClient, admin_token: str, student_token: str
):
    create_resp = await client.post(
        "/api/subjects",
        json={"code": "DASH_G", "name": "Dashboard Graph"},
        headers=auth_header(admin_token),
    )
    subject_id = create_resp.json()["id"]
    await client.post(
        f"/api/subjects/{subject_id}/enroll",
        headers=auth_header(student_token),
    )

    resp = await client.get(
        f"/api/dashboard/concept-graph?subject_id={subject_id}",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
