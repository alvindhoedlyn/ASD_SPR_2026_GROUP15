"""Client for the shared, local, non-containerised MCP server."""

import asyncio
import json
import os
from typing import Any


def mcp_enabled() -> bool:
    return os.getenv("MCP_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def mcp_server_url() -> str:
    return os.getenv("MCP_SERVER_URL", "http://host.docker.internal:5200/mcp")


def _normalise_result(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        dumped = result.model_dump(by_alias=True)
        structured = dumped.get("structuredContent") or dumped.get("structured_content")
        if isinstance(structured, dict):
            return structured
        content = dumped.get("content") or []
    else:
        content = getattr(result, "content", []) or []

    text_parts = []
    for block in content:
        if isinstance(block, dict):
            value = block.get("text")
        else:
            value = getattr(block, "text", None)
        if value:
            text_parts.append(value)

    combined = "\n".join(text_parts).strip()
    if combined:
        try:
            parsed = json.loads(combined)
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except json.JSONDecodeError:
            return {"status": "success", "result": combined}
    return {"status": "success", "result": None}


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(mcp_server_url()) as (read_stream, write_stream, *_):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return _normalise_result(result)


def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if not mcp_enabled():
        raise RuntimeError("MCP mode is disabled")
    return asyncio.run(_call_tool(tool_name, arguments))
