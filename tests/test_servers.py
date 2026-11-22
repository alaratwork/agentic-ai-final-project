# file:     tests/test_servers.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  the capability server starts over stdio and serves identical a/b tools
# updated:  2026-11-22

from __future__ import annotations

import asyncio
import json

from fastmcp import Client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from harness.capabilities.base import EXPLICIT_ERROR
from harness.servers import build_server, stdio_connection

FC01 = {"town": "Brennick", "date": "2026-12-01"}


async def _stdio_roundtrip():
    # launch - the same subprocess command the agent uses
    conn = stdio_connection("forecast")
    params = StdioServerParameters(command=conn["command"], args=conn["args"],
                                   cwd=conn["cwd"], env=conn["env"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            result = await session.call_tool("forecast_lookup_a", FC01)
            return tools, result


def test_stdio_server_lists_identical_pair_and_answers():
    tools, result = asyncio.run(_stdio_roundtrip())
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {"forecast_lookup_a", "forecast_lookup_b"}
    # check - a and b share one schema, so only descriptions can differ later
    assert by_name["forecast_lookup_a"].inputSchema == by_name["forecast_lookup_b"].inputSchema
    assert not result.isError
    payload = json.loads(result.content[0].text)
    assert payload["status"] == "ok" and payload["high_c"] == 5.6


async def _call_in_memory(decide):
    # serve - in-process, so a test can force an outcome without a fault schedule
    async with Client(build_server("forecast", decide=decide)) as client:
        return await client.call_tool("forecast_lookup_b", FC01, raise_on_error=False)


def test_explicit_error_reaches_client_verbatim():
    result = asyncio.run(_call_in_memory(lambda tool: "explicit"))
    assert result.is_error
    assert result.content[0].text == EXPLICIT_ERROR


def test_model_mistakes_do_not_use_up_scheduled_outcomes():
    # check - bad args return before decide(), so only valid calls are counted
    seen = []

    def counting(tool):
        seen.append(tool)
        return "clean"

    async def calls():
        async with Client(build_server("forecast", decide=counting)) as client:
            await client.call_tool("forecast_lookup_a", {"town": "Brennick", "date": "Dec 1"})
            await client.call_tool("forecast_lookup_a", {"town": "Atlantis", "date": "2026-12-01"})
            await client.call_tool("forecast_lookup_a", FC01)
    asyncio.run(calls())
    assert seen == ["forecast_lookup_a"]


async def _stdio_call(fault_args):
    # launch - a subprocess server with a fault schedule from command-line flags
    conn = stdio_connection("forecast", fault_args)
    params = StdioServerParameters(command=conn["command"], args=conn["args"],
                                   cwd=conn["cwd"], env=conn["env"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return [await session.call_tool(t, FC01) for t in
                    ("forecast_lookup_a", "forecast_lookup_a", "forecast_lookup_b")]


def test_stdio_server_applies_its_fault_schedule():
    fault = {"episode_id": "t-1", "flawed_tool": "forecast_lookup_a",
             "flaw_type": "explicit", "mode": "prefilled"}
    a1, a2, b = asyncio.run(_stdio_call(fault))
    assert a1.isError and a1.content[0].text == EXPLICIT_ERROR
    assert a2.isError  # prefilled: fails on every call
    assert not b.isError and json.loads(b.content[0].text)["high_c"] == 5.6


def test_silent_outcome_is_ok_but_wrong():
    result = asyncio.run(_call_in_memory(lambda tool: "silent"))
    payload = json.loads(result.content[0].text)
    assert not result.is_error and payload["status"] == "ok"
    assert payload["high_c"] != 5.6
