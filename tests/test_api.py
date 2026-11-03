"""The FastAPI surface, exercised through the app directly (no network)."""

import pytest
from fastapi.testclient import TestClient

from plain_language_desk.main import app

client = TestClient(app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_ping():
    # AgentCore Runtime's health probe path.
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_score_endpoint_returns_the_report_with_the_ruleset_ref():
    resp = client.post("/score", json={"text": "Short active sentence. You can read it in one pass."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "WPS/1.2"
    assert body["band"] in {"green", "pass", "concerns", "fail", "exempt"}
    assert body["ruleset"] == "faa-plain-language@1.0.0"
    assert body["bar"] == 80


def test_score_endpoint_rejects_empty_text():
    resp = client.post("/score", json={"text": "   "})
    assert resp.status_code == 422


def test_improve_endpoint_validates_round_bounds():
    resp = client.post("/improve", json={"text": "Hello there.", "max_rounds": 9})
    assert resp.status_code == 422


def test_improve_endpoint_validates_mode():
    resp = client.post("/improve", json={"text": "Hello there.", "mode": "aggressive"})
    assert resp.status_code == 422


def test_improve_endpoint_reports_unconfigured_engine_as_503(monkeypatch):
    monkeypatch.delenv("INFERENCE_BASE_URL", raising=False)
    monkeypatch.delenv("INFERENCE_MODEL", raising=False)
    resp = client.post("/improve", json={"text": "Hello there."})
    assert resp.status_code == 503
    # The detail is a fixed string: internals (env names, scorer stderr,
    # input snippets) are logged server-side, never returned (THREAT-MODEL
    # TB1-8). Assert the fixed contract AND the absence of internals.
    assert resp.json()["detail"] == "scoring failed; see server logs"
