"""JSON bridge executed only by the isolated weather Python environment."""

import asyncio
import json
import sys
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def query(payload):
    params = StdioServerParameters(command=sys.executable, args=["-m", "src.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=20)
        ) as session:
            await session.initialize()
            result = await session.call_tool("get_weather_forecast", payload)
            if result.isError:
                raise ValueError("weather_tool_failed")
            return result.structuredContent or json.loads(
                next(item.text for item in result.content if item.type == "text")
            )


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(asyncio.wait_for(query(json.load(sys.stdin)), 25))))
    except Exception:
        print('{"error":"weather_unavailable"}')
        sys.exit(1)
