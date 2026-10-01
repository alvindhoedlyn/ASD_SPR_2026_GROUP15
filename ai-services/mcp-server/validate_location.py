"""
Terminal validation client for the shared attraction MCP tools.
"""

import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import (
    streamable_http_client
)


MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://localhost:5200/mcp"
)


async def main():
    async with streamable_http_client(
        MCP_SERVER_URL
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

            available_tools = await session.list_tools()

            print("Registered tools:")

            for tool in available_tools.tools:
                print(f"- {tool.name}")

            city_result = await session.call_tool(
                "attractions_by_city",
                {
                    "city": "Sydney",
                    "category": "nature"
                }
            )

            print("\nattractions_by_city result:")
            print(json.dumps(
                city_result.model_dump(mode="json"),
                indent=2
            ))

            details_result = await session.call_tool(
                "attraction_details",
                {
                    "attraction_id": 1
                }
            )

            print("\nattraction_details result:")
            print(json.dumps(
                details_result.model_dump(mode="json"),
                indent=2
            ))


if __name__ == "__main__":
    asyncio.run(main())