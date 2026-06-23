"""Tests for /standups endpoints."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.models.standup_entry import StandupEntry


# ── Auth guard tests ────────────────────────────────────────────────────────────

def test_create_standup_no_auth(client: TestClient) -> None:
    resp = client.post("/standups", json={
        "team_member": "Alice",
        "standup_date": "2025-06-16",
        "yesterday": "Did stuff.",
        "today": "Doing stuff.",
    })
    assert resp.status_code == 401


def test_list_standups_no_auth(client: TestClient) -> None:
    resp = client.get("/standups")
    assert resp.status_code == 401


def test_create_standup_wrong_key(client: TestClient) -> None:
    resp = client.post(
        "/standups",
        json={"team_member": "Alice", "standup_date": "2025-06-16",
              "yesterday": "A", "today": "B"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


# ── CRUD tests ───────────────────────────────────────────────────────────────────

def test_create_standup_201(client: TestClient, api_headers: dict) -> None:
    resp = client.post(
        "/standups",
        json={
            "team_member": "Alice",
            "standup_date": "2025-06-16",
            "yesterday": "Completed router tests.",
            "today": "Write integration tests.",
            "blockers": None,
        },
        headers=api_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["team_member"] == "Alice"
    assert data["standup_date"] == "2025-06-16"
    assert "id" in data
    assert "created_at" in data


def test_create_standup_with_blockers(client: TestClient, api_headers: dict) -> None:
    resp = client.post(
        "/standups",
        json={
            "team_member": "Bob",
            "standup_date": "2025-06-17",
            "yesterday": "Set up Streamlit.",
            "today": "Wire API calls.",
            "blockers": "Waiting for RDS access.",
        },
        headers=api_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["blockers"] == "Waiting for RDS access."


def test_list_standups_empty(client: TestClient, api_headers: dict) -> None:
    resp = client.get("/standups", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_list_standups_with_entry(client: TestClient, api_headers: dict, sample_entry: StandupEntry) -> None:
    resp = client.get("/standups", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["team_member"] == "Alice"


def test_list_standups_filter_by_member(client: TestClient, api_headers: dict, sample_entry: StandupEntry) -> None:
    resp = client.get("/standups?team_member=Alice", headers=api_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp2 = client.get("/standups?team_member=Bob", headers=api_headers)
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


def test_list_standups_date_filter(client: TestClient, api_headers: dict, sample_entry: StandupEntry) -> None:
    resp = client.get("/standups?date_from=2025-06-16&date_to=2025-06-16", headers=api_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp2 = client.get("/standups?date_from=2025-06-17", headers=api_headers)
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


def test_get_standup_200(client: TestClient, api_headers: dict, sample_entry: StandupEntry) -> None:
    resp = client.get(f"/standups/{sample_entry.id}", headers=api_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == str(sample_entry.id)


def test_get_standup_404(client: TestClient, api_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/standups/{fake_id}", headers=api_headers)
    assert resp.status_code == 404


def test_delete_standup_204(client: TestClient, api_headers: dict, sample_entry: StandupEntry) -> None:
    resp = client.delete(f"/standups/{sample_entry.id}", headers=api_headers)
    assert resp.status_code == 204
    # Confirm gone
    resp2 = client.get(f"/standups/{sample_entry.id}", headers=api_headers)
    assert resp2.status_code == 404


def test_delete_standup_404(client: TestClient, api_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    resp = client.delete(f"/standups/{fake_id}", headers=api_headers)
    assert resp.status_code == 404


def test_list_standups_pagination(client: TestClient, api_headers: dict, db_session: object) -> None:
    # Create via API so the cleanup runs properly
    for i in range(3):
        client.post(
            "/standups",
            json={
                "team_member": f"Member{i}",
                "standup_date": "2025-06-16",
                "yesterday": "A",
                "today": "B",
            },
            headers=api_headers,
        )
    resp = client.get("/standups?limit=2&offset=0", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
