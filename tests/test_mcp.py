"""The native MCP surface, exercised through the in-memory FastMCP client."""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from plain_language_desk.mcp_surface import mcp


async def test_score_prose_tool_returns_the_report():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "score_prose", {"text": "Short active sentence. You can read it in one pass."}
        )
    data = result.data
    assert data["score"] >= 80
    assert data["ruleset"] == "faa-plain-language@1.0.0"
    assert data["bar"] == 80


async def test_improve_prose_tool_reports_unconfigured_engine():
    with pytest.raises(ToolError) as exc_info:
        async with Client(mcp) as client:
            await client.call_tool("improve_prose", {"text": "Hello there."})
    assert "INFERENCE_BASE_URL" in str(exc_info.value)


async def test_tools_are_listed():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools} == {"score_prose", "improve_prose"}
