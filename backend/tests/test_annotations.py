"""Integration tests for collaborative material annotations (Future Work item #9)."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


async def _make_subject(client: AsyncClient, admin_token: str, code: str) -> str:
    resp = await client.post(
        "/api/subjects",
        json={"code": code, "name": code.title()},
        headers=auth_header(admin_token),
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_and_list_annotation(
    client: AsyncClient, admin_token: str, student_token: str
):
    subject_id = await _make_subject(client, admin_token, "ANNOT_A")

    create_resp = await client.post(
        "/api/annotations",
        json={
            "subject_id": subject_id,
            "source_file": "chapter1.pdf",
            "page": 3,
            "note": "This paragraph explains recursion well.",
            "highlight_text": "a function calling itself",
        },
        headers=auth_header(student_token),
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["source_file"] == "chapter1.pdf"
    assert body["page"] == 3
    assert body["note"] == "This paragraph explains recursion well."

    list_resp = await client.get(
        f"/api/annotations?subject_id={subject_id}",
        headers=auth_header(student_token),
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["note"] == "This paragraph explains recursion well."


@pytest.mark.asyncio
async def test_list_filters_by_page(
    client: AsyncClient, admin_token: str, student_token: str
):
    subject_id = await _make_subject(client, admin_token, "ANNOT_B")

    for page in (1, 2, 2):
        await client.post(
            "/api/annotations",
            json={
                "subject_id": subject_id,
                "source_file": "notes.pdf",
                "page": page,
                "note": f"note on page {page}",
            },
            headers=auth_header(student_token),
        )

    resp = await client.get(
        f"/api/annotations?subject_id={subject_id}&source_file=notes.pdf&page=2",
        headers=auth_header(student_token),
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert all(i["page"] == 2 for i in items)


@pytest.mark.asyncio
async def test_delete_own_annotation(
    client: AsyncClient, admin_token: str, student_token: str
):
    subject_id = await _make_subject(client, admin_token, "ANNOT_C")

    create_resp = await client.post(
        "/api/annotations",
        json={"subject_id": subject_id, "source_file": "x.pdf", "page": 0, "note": "temp"},
        headers=auth_header(student_token),
    )
    annotation_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/annotations/{annotation_id}", headers=auth_header(student_token)
    )
    assert delete_resp.status_code == 200

    list_resp = await client.get(
        f"/api/annotations?subject_id={subject_id}", headers=auth_header(student_token)
    )
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_cannot_delete_others_annotation(
    client: AsyncClient, admin_token: str, student_token: str, test_student
):
    subject_id = await _make_subject(client, admin_token, "ANNOT_D")

    create_resp = await client.post(
        "/api/annotations",
        json={"subject_id": subject_id, "source_file": "x.pdf", "page": 0, "note": "mine"},
        headers=auth_header(admin_token),
    )
    annotation_id = create_resp.json()["id"]

    # A different, non-owning student cannot delete an admin's annotation.
    delete_resp = await client.delete(
        f"/api/annotations/{annotation_id}", headers=auth_header(student_token)
    )
    assert delete_resp.status_code == 403
