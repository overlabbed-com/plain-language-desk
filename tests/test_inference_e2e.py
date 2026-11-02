"""End-to-end inference: a real OpenAI-compatible HTTP round-trip.

No SDK, no mocking of the client internals — a localhost server speaks the
chat-completions wire format, and the service's own httpx client completes a
successful call through the full /improve flow, exactly as it would against
the homelab gateway, vLLM, or any OpenAI-compatible endpoint.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi.testclient import TestClient

from plain_language_desk.main import app

BAD = (
    "It shall be noted that the aforementioned provisions are required to be verified "
    "by the addressees prior to the commencement of the undertaking of the work."
)
GOOD = "Verify the provisions before starting the work. The addressees get the checklist today."

client = TestClient(app)


class _FakeOpenAI(BaseHTTPRequestHandler):
    """Speaks POST /v1/chat/completions with an OpenAI-shaped response body."""

    received: list[dict] = []

    def do_POST(self):  # noqa: N802 - stdlib handler naming
        assert self.path.endswith("/chat/completions"), self.path
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.received.append(body)
        payload = json.dumps(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": GOOD},
                    }
                ],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # silence the test log
        pass


def test_improve_completes_a_real_inference_call_end_to_end(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenAI)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/v1"
        monkeypatch.setenv("INFERENCE_BASE_URL", base)
        monkeypatch.setenv("INFERENCE_MODEL", "fake-model")
        monkeypatch.delenv("INFERENCE_API_KEY", raising=False)

        resp = client.post("/improve", json={"text": BAD, "mode": "full"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["final_score"] >= body["bar"]
        assert body["text"] == GOOD
        assert body["rounds"] == 1

        # The wire request was plain OpenAI chat-completions JSON — nothing else.
        sent = _FakeOpenAI.received[-1]
        assert sent["model"] == "fake-model"
        assert [m["role"] for m in sent["messages"]] == ["system", "user"]
        assert "aforementioned" in sent["messages"][1]["content"]
    finally:
        server.shutdown()
        server.server_close()


class _ReasoningOpenAI(_FakeOpenAI):
    """gpt-oss-on-Bedrock shape: the analysis channel rides inside content."""

    def do_POST(self):  # noqa: N802 - stdlib handler naming
        self.rfile.read(int(self.headers["Content-Length"]))
        payload = json.dumps(
            {
                "id": "chatcmpl-reasoning",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": (
                                "<reasoning>The text is passive and archaic. "
                                "Rewrite it actively without 'shall' or "
                                "'aforementioned'.</reasoning>"
                                + GOOD
                            ),
                        },
                    }
                ],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def test_improve_strips_engine_reasoning_blocks(monkeypatch):
    """A reasoning model must not have its thinking scored as prose."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ReasoningOpenAI)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/v1"
        monkeypatch.setenv("INFERENCE_BASE_URL", base)
        monkeypatch.setenv("INFERENCE_MODEL", "reasoning-model")
        monkeypatch.delenv("INFERENCE_API_KEY", raising=False)

        resp = client.post("/improve", json={"text": BAD, "mode": "full"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == GOOD
        assert "<reasoning>" not in body["text"]
        assert "reasoning" not in body["text"]
        assert body["final_score"] >= body["bar"]
    finally:
        server.shutdown()
        server.server_close()
