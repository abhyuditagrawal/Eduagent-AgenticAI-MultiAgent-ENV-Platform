"""Integration tests for the knowledge-tracing API endpoints, including the
new personalised-BKT and outcome-prediction routes (Future Work items #2, #6).
"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_bkt_params_default_before_fitting(client: AsyncClient, student_token: str):
    resp = await client.get("/api/knowledge-tracing/params", headers=auth_header(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["personalized"] is False
    assert set(data["p_transit"].keys()) == {"1", "2", "3"} or set(data["p_transit"].keys()) == {1, 2, 3}


@pytest.mark.asyncio
async def test_fit_params_not_enough_observations(client: AsyncClient, student_token: str):
    resp = await client.post("/api/knowledge-tracing/fit-params", headers=auth_header(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["fitted"] is False
    assert data["reason"] == "not_enough_observations"


@pytest.mark.asyncio
async def test_outcome_prediction_no_concepts_yet(
    client: AsyncClient, admin_token: str, student_token: str
):
    subject_resp = await client.post(
        "/api/subjects",
        json={"code": "OUTCOME_A", "name": "Outcome A"},
        headers=auth_header(admin_token),
    )
    subject_id = subject_resp.json()["id"]

    resp = await client.get(
        f"/api/knowledge-tracing/outcome-prediction?subject_id={subject_id}",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["predicted_score"] is None
    assert data["concepts"] == []


@pytest.mark.asyncio
async def test_outcome_prediction_with_custom_exam_date(
    client: AsyncClient, admin_token: str, student_token: str
):
    subject_resp = await client.post(
        "/api/subjects",
        json={"code": "OUTCOME_B", "name": "Outcome B"},
        headers=auth_header(admin_token),
    )
    subject_id = subject_resp.json()["id"]

    resp = await client.get(
        f"/api/knowledge-tracing/outcome-prediction?subject_id={subject_id}&exam_date=2030-01-01T00:00:00",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exam_date"].startswith("2030-01-01")
