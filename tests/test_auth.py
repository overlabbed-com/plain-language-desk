"""Optional bearer auth: set AUTH_TOKEN and every path except /healthz needs it."""

import pytest
from fastapi.testclient import TestClient

from plain_language_desk.main import app

client = TestClient(app)


def test_open_when_no_token_is_configured(monkeypatch):
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    assert client.get("/healthz").status_code == 200
    assert client.post("/score", json={"text": "Short active sentence."}).status_code == 200


def test_token_required_when_configured(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "sekrit")
    assert client.post("/score", json={"text": "Short active sentence."}).status_code == 401
    assert (
        client.post(
            "/score",
            json={"text": "Short active sentence."},
            headers={"Authorization": "Bearer wrong"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/score",
            json={"text": "Short active sentence."},
            headers={"Authorization": "Bearer sekrit"},
        ).status_code
        == 200
    )
    # Probes stay open so a load balancer or kubelet can health-check.
    assert client.get("/healthz").status_code == 200
