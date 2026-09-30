"""
MCP client for the shared local MCP server.

The Budget Tracker backend uses this client to communicate
with the group's shared MCP server through Streamable HTTP.
"""

import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://host.docker.internal:5200/mcp",
)


def _parse_mcp_result(result):
    """
    Convert MCP text content into normal Python objects.
    """
    values = []

    for content in result.content:
        text = getattr(content, "text", None)

        if text is None:
            continue

        try:
            values.append(json.loads(text))
        except json.JSONDecodeError:
            values.append(text)

    if len(values) == 1:
        return values[0]

    return values


async def _call_tool_async(tool_name, arguments=None):
    """
    Connect to the shared MCP server and call one MCP tool.
    """
    async with streamable_http_client(MCP_SERVER_URL) as (
        read,
        write,
        _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments=arguments or {},
            )

            return _parse_mcp_result(result)


def call_mcp_tool(tool_name, arguments=None):
    """
    Synchronous wrapper for Flask routes.
    """
    return asyncio.run(
        _call_tool_async(
            tool_name,
            arguments,
        )
    )


def get_budget_summary_via_mcp():
    """
    Get Budget Tracker summary through the shared MCP server.
    """
    return call_mcp_tool(
        "budget_summary",
        {},
    )


def get_budget_expenses_via_mcp():
    """
    Get Budget Tracker expenses through the shared MCP server.
    """
    return call_mcp_tool(
        "budget_expenses",
        {},
    )
