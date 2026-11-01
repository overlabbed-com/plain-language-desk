"""Entrypoint: uvicorn with a drain shorter than the pod's 30 s termination
grace, so a running request cancels cleanly instead of meeting SIGKILL.
Same pattern as the homelab log-triage service."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "plain_language_desk.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        log_level=os.environ.get("LOG_LEVEL", "INFO").lower(),
        timeout_graceful_shutdown=20,
    )
