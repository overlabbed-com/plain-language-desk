"""FastAPI surface: /healthz, /score, /improve, plus the MCP surface mounted at /mcp.

Stateless by contract: nothing persists, nothing writes outside /tmp, and the
response always returns to the caller. Optional bearer auth via AUTH_TOKEN —
whoever hosts the desk locks it with one env var.
"""

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .improve import OpenAICompatClient, improve_text
from .mcp_surface import mcp
from .ruleset import VALID_MODES, current as current_ruleset
from .scorer import MAX_TEXT_CHARS, score_text

app = FastAPI(title="plain-language-desk", version="0.1.0")


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    token = os.environ.get("AUTH_TOKEN", "").strip()
    if token and request.url.path != "/healthz":
        if request.headers.get("authorization", "") != f"Bearer {token}":
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


def _not_blank(v: str) -> str:
    if not v.strip():
        raise ValueError("text must not be blank")
    return v


class ScoreRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        return _not_blank(v)


class ImproveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    mode: str = "full"
    audience: str = ""
    max_rounds: int | None = Field(default=None, ge=1, le=5)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        return _not_blank(v)

    @field_validator("mode")
    @classmethod
    def mode_valid(cls, v: str) -> str:
        if v not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}")
        return v


def _default_rounds() -> int:
    return max(1, min(5, int(os.environ.get("MAX_ROUNDS", "3"))))


def _http_error(exc: Exception, status: int = 502) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc)[:300])


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True}


@app.post("/score")
async def score(req: ScoreRequest) -> dict[str, Any]:
    rs = current_ruleset()
    try:
        report = await score_text(req.text)
    except (RuntimeError, ValueError) as exc:
        raise _http_error(exc) from exc
    return {**report, "ruleset": rs.ref, "bar": rs.bar}


@app.post("/improve")
async def improve(req: ImproveRequest) -> dict[str, Any]:
    rs = current_ruleset()
    try:
        client = OpenAICompatClient.from_env()
    except RuntimeError as exc:
        # Unconfigured engine is a hosting problem, not a downstream failure.
        raise _http_error(exc, status=503) from exc
    try:
        return await improve_text(
            req.text,
            req.audience,
            req.max_rounds if req.max_rounds is not None else _default_rounds(),
            req.mode,
            client,
            rs.prompt(req.mode),
            rs.bar,
            rs.ref,
        )
    except (RuntimeError, ValueError) as exc:
        raise _http_error(exc) from exc


# The MCP surface mounts last so the API routes above match first; FastMCP
# serves streamable-http at /mcp inside the mounted ASGI app. Its lifespan
# must own the parent app's lifespan, or the session manager never starts.
_mcp_asgi = mcp.streamable_http_app() if hasattr(mcp, "streamable_http_app") else mcp.http_app()
app.router.lifespan_context = _mcp_asgi.lifespan
app.mount("/", _mcp_asgi)
