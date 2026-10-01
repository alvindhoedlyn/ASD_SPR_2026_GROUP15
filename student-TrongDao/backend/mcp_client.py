import asyncio
from datetime import timedelta

from mcp import ClientSession
from mcp.client.streamable_http import (
    streamable_http_client
)


async def _call_mcp_tool(
    server_url,
    tool_name,
    arguments,
    timeout_seconds
):
    async with streamable_http_client(
        server_url
    ) as (
        read_stream,
        write_stream,
        _
    ):
        async with ClientSession(
            read_stream,
            write_stream
        ) as session:
            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments,
                read_timeout_seconds=timedelta(
                    seconds=timeout_seconds
                )
            )

            return result.model_dump(mode="json")


def call_mcp_tool(
    server_url,
    tool_name,
    arguments,
    timeout_seconds=30
):
    return asyncio.run(
        _call_mcp_tool(
            server_url,
            tool_name,
            arguments,
            timeout_seconds
        )
    )