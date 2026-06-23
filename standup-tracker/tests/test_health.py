"""Tests for GET /health."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"


def test_health_no_auth_required(client: TestClient) -> None:
    """GET /health must not require API key."""
    resp = client.get("/health")
    assert resp.status_code == 200
