"""Tests for /summaries endpoints."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.models.weekly_summary import WeeklySummary


@pytest.fixture()
def mock_bedrock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock Bedrock at the router import site."""
    fake = MagicMock()
    fake.invoke_text.return_value = (
        "## Team Summary\nGood week.\n"
        "## Per-Member Updates\n**Alice** Done.\n"
        "## Blockers\nNone reported.\n"
        "## Key Achievements\nShipped feature."
    )
    monkeypatch.setattr(
        "app.routers.summaries.get_bedrock_client", lambda: fake
    )
    return fake


# ── Auth guard ──────────────────────────────────────────────────────────────────

def test_generate_summary_no_auth(client: TestClient) -> None:
    resp = client.post(
        "/summaries/generate",
        json={"week_start": "2025-06-16", "week_end": "2025-06-20"},
    )
    assert resp.status_code == 401


def test_list_summaries_no_auth(client: TestClient) -> None:
    resp = client.get("/summaries")
    assert resp.status_code == 401


# ── Generate summary ──────────────────────────────────────────────────────────────

def test_generate_summary_201(
    client: TestClient,
    api_headers: dict,
    mock_bedrock: MagicMock,
    sample_entry: object,
) -> None:
    resp = client.post(
        "/summaries/generate",
        json={"week_start": "2025-06-16", "week_end": "2025-06-20"},
        headers=api_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["week_start"] == "2025-06-16"
    assert data["week_end"] == "2025-06-20"
    assert "## Team Summary" in data["summary_markdown"]
    assert mock_bedrock.invoke_text.called


def test_generate_summary_empty_range(
    client: TestClient,
    api_headers: dict,
    mock_bedrock: MagicMock,
) -> None:
    """FR-6: no entries still returns 201 with a generated summary."""
    mock_bedrock.invoke_text.return_value = "## No Data\nNo standup entries found for this range."
    resp = client.post(
        "/summaries/generate",
        json={"week_start": "2020-01-01", "week_end": "2020-01-05"},
        headers=api_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "## No Data" in data["summary_markdown"]


# ── List + Get summaries ─────────────────────────────────────────────────────────

def test_list_summaries_empty(client: TestClient, api_headers: dict) -> None:
    resp = client.get("/summaries", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_summaries_with_entry(
    client: TestClient, api_headers: dict, sample_summary: WeeklySummary
) -> None:
    resp = client.get("/summaries", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["week_start"] == "2025-06-09"


def test_get_summary_200(
    client: TestClient, api_headers: dict, sample_summary: WeeklySummary
) -> None:
    resp = client.get(f"/summaries/{sample_summary.id}", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(sample_summary.id)
    assert "## Team Summary" in data["summary_markdown"]


def test_get_summary_404(client: TestClient, api_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/summaries/{fake_id}", headers=api_headers)
    assert resp.status_code == 404


def test_list_summaries_pagination(
    client: TestClient,
    api_headers: dict,
    mock_bedrock: MagicMock,
) -> None:
    # Generate 3 summaries
    for i in range(3):
        client.post(
            "/summaries/generate",
            json={"week_start": f"2025-0{i+1}-01", "week_end": f"2025-0{i+1}-05"},
            headers=api_headers,
        )
    resp = client.get("/summaries?limit=2&offset=0", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
