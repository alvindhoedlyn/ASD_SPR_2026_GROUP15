"""
student-RenzoRobin/backend/mcp_client.py

A real MCP client, bridging Flask's synchronous routes to the MCP Python
SDK's async ClientSession. Connects to the shared, non-containerised MCP
server over streamable-http (the real MCP wire protocol), replacing the
earlier shortcut that bypassed the MCP server and queried the database
directly.

Requires "mcp" in backend/requirements.txt (same package the MCP server
itself uses).
"""
import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# host.docker.internal because this backend runs in Docker while the MCP
# server runs directly on the host (non-containerised, same reasoning as
# RAG_SERVICE_URL). /mcp matches the server's streamable_http_path.
MCP_SERVICE_URL = os.environ.get("MCP_SERVICE_URL", "http://host.docker.internal:5200/mcp")
MCP_CALL_TIMEOUT_SECONDS = int(os.environ.get("MCP_CALL_TIMEOUT_SECONDS", "30"))


class MCPClientError(Exception):
    """Raised when the MCP server is unreachable or returns a tool-level error."""


async def _call_tool_async(tool_name: str, arguments: dict):
    async with streamable_http_client(MCP_SERVICE_URL) as (read, write, *_extra):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            if result.isError:
                detail = result.content[0].text if result.content else "unknown tool error"
                raise MCPClientError(f"MCP tool '{tool_name}' returned an error: {detail}")

            # Prefer structuredContent (a typed dict) when the server provides
            # it; otherwise fall back to parsing the text content block as
            # JSON, which is how FastMCP serialises plain Python return
            # values (list/dict) when no output schema is declared.
            if result.structuredContent is not None:
                return result.structuredContent

            if result.content:
                text = result.content[0].text
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return text

            return None


def _flatten_exception_group(exc: BaseException) -> list[str]:
    """
    asyncio TaskGroups (used internally by the MCP client's transport)
    wrap failures in an ExceptionGroup, whose str() is a useless generic
    summary ("unhandled errors in a TaskGroup (N sub-exception)"). This
    recursively pulls out the real underlying exception(s) so callers see
    the actual cause (connection refused, handshake failure, etc.).
    """
    if isinstance(exc, BaseExceptionGroup):
        flattened = []
        for sub in exc.exceptions:
            flattened.extend(_flatten_exception_group(sub))
        return flattened
    return [f"{type(exc).__name__}: {exc}"]


def call_mcp_tool(tool_name: str, arguments: dict):
    """
    Synchronous entry point for Flask routes. Raises MCPClientError with
    the real underlying cause (not a generic TaskGroup wrapper message)
    on any failure — callers should catch MCPClientError broadly.
    """
    try:
        return asyncio.run(asyncio.wait_for(_call_tool_async(tool_name, arguments), timeout=MCP_CALL_TIMEOUT_SECONDS))
    except MCPClientError:
        raise
    except BaseExceptionGroup as eg:
        messages = _flatten_exception_group(eg)
        raise MCPClientError("; ".join(messages)) from eg
    except Exception as exc:
        raise MCPClientError(f"{type(exc).__name__}: {exc}") from exc