# file:     tests/test_servers.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  the capability server starts over stdio and serves identical a/b tools
# updated:  2026-11-23

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml
from fastmcp import Client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from harness.capabilities import CAPABILITIES
from harness.capabilities.base import EXPLICIT_ERROR
from harness.descriptions import render
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


TASKS = yaml.safe_load((Path(__file__).resolve().parents[1] / "data/tasks/tasks.yaml").read_text())["tasks"]


async def _stdio_pair(name, a, b, args, flaw_type):
    # launch - this capability's server with tool a flawed on every call
    fault = {"episode_id": "t-2", "flawed_tool": a, "flaw_type": flaw_type, "mode": "prefilled"}
    conn = stdio_connection(name, fault)
    params = StdioServerParameters(command=conn["command"], args=conn["args"],
                                   cwd=conn["cwd"], env=conn["env"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            return tools, await session.call_tool(a, args), await session.call_tool(b, args)


@pytest.mark.parametrize("name", sorted(CAPABILITIES))
def test_every_capability_server_works_over_stdio(name):
    cap = CAPABILITIES[name]()
    args = next(t for t in TASKS if t["capability"] == name)["args"]
    a, b = f"{cap.tool_stem}_a", f"{cap.tool_stem}_b"
    clean = cap.lookup(**args)
    # explicit - a returns the exact 503; b stays clean and matches the oracle
    tools, ra, rb = asyncio.run(_stdio_pair(name, a, b, args, "explicit"))
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {a, b}
    assert by_name[a].inputSchema == by_name[b].inputSchema
    assert ra.isError and ra.content[0].text == EXPLICIT_ERROR
    assert json.loads(rb.content[0].text) == clean
    # silent - a returns exactly the designed perturbation, labelled ok
    _, ra, _ = asyncio.run(_stdio_pair(name, a, b, args, "silent"))
    assert not ra.isError and json.loads(ra.content[0].text) == cap.perturb(args, clean)


async def _stdio_descriptions(styles):
    # launch - the style flags must reach the subprocess server
    conn = stdio_connection("staff", styles=styles)
    params = StdioServerParameters(command=conn["command"], args=conn["args"],
                                   cwd=conn["cwd"], env=conn["env"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return {t.name: t.description for t in (await session.list_tools()).tools}


def test_stdio_server_shows_the_requested_styles():
    shown = asyncio.run(_stdio_descriptions({"a": "poor", "b": "rich"}))
    assert shown["staff_lookup_a"] == render("staff", "poor")
    assert shown["staff_lookup_b"] == render("staff", "rich")


def test_silent_outcome_is_ok_but_wrong():
    result = asyncio.run(_call_in_memory(lambda tool: "silent"))
    payload = json.loads(result.content[0].text)
    assert not result.is_error and payload["status"] == "ok"
    assert payload["high_c"] != 5.6
