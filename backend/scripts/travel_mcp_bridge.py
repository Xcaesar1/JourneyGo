"""Isolated MCP client. Only the three approved read-only tools can be invoked."""

import asyncio
import json
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

logging.disable(logging.CRITICAL)
TOOLS = {"train": "get-tickets", "hotel": "searchHotels", "flight": "getFlightPriceByCities"}


async def call(read, write, kind, arguments):
    async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=35)) as session:
        await session.initialize()
        result = await session.call_tool(TOOLS[kind], arguments)
        if result.isError:
            raise ValueError("provider_error")
        if result.structuredContent is not None:
            return result.structuredContent
        return json.loads(next(item.text for item in result.content if item.type == "text"))


async def query(payload):
    kind = payload["provider"]
    if kind not in TOOLS:
        raise ValueError("unsupported_provider")
    if kind == "hotel":
        async with streamablehttp_client(
            "https://mcp.rollinggo.cn/mcp",
            headers={"Authorization": "Bearer " + os.environ["ROLLINGGO_API_KEY"]},
            timeout=35,
            sse_read_timeout=35,
        ) as (read, write, _):
            return await call(read, write, kind, payload["arguments"])
    package, entry = (
        ("12306-mcp", "build/index.js")
        if kind == "train"
        else ("@variflight-ai/variflight-mcp", "dist/index.js")
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "HOME",
            "LANG",
        }
    }
    if kind == "flight":
        env["VARIFLIGHT_API_KEY"] = os.environ["VARIFLIGHT_API_KEY"]
    params = StdioServerParameters(
        command=os.environ.get("TRAVEL_MCP_NODE", "node"),
        args=[str(Path(os.environ["TRAVEL_MCP_MODULES"]) / package / entry)],
        env=env,
    )
    with open(os.devnull, "w") as err:
        async with stdio_client(params, errlog=err) as (read, write):
            return await call(read, write, kind, payload["arguments"])


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(asyncio.wait_for(query(json.load(sys.stdin)), 40))))
    except Exception:
        # Never print third-party exception messages, headers, or credential-bearing URLs.
        print('{"error":"travel_provider_unavailable"}')
        sys.exit(1)
