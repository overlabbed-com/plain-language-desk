"""Native MCP surface: any MCP-speaking harness calls the desk directly.

FastMCP tools mirror the HTTP operations. In the homelab this replaces the
separate -mcp facade; elsewhere it is the only surface a harness needs.
"""

from typing import Any

from fastmcp import FastMCP

from .improve import OpenAICompatClient, improve_text
from .ruleset import VALID_MODES, current as current_ruleset
from .scorer import score_text

mcp = FastMCP("plain-language-desk")


@mcp.tool
async def score_prose(text: str) -> dict[str, Any]:
    """Grade prose against the active ruleset. Deterministic; changes nothing."""
    rs = current_ruleset()
    report = await score_text(text)
    return {**report, "ruleset": rs.ref, "bar": rs.bar}


@mcp.tool
async def improve_prose(
    text: str,
    mode: str = "full",
    audience: str = "",
    max_rounds: int = 3,
) -> dict[str, Any]:
    """Return the prose rewritten to the bar.

    mode=minimal fixes the violations only; mode=full rewrites for style.
    Both run the same deterministic-scored loop.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    rs = current_ruleset()
    client = OpenAICompatClient.from_env()
    return await improve_text(
        text, audience, max_rounds, mode, client, rs.prompt(mode), rs.bar, rs.ref
    )
