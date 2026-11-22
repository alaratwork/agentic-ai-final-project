# file:     harness/agent.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  langgraph tool-calling loop (agent -> tools -> agent) over mcp stdio servers
# updated:  2026-11-22

from __future__ import annotations

import json
import operator
import time
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from typing import Annotated, Sequence, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

STEP_CAP = 10  # one step = one model call (fp2 4.2)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # appended, never replaced
    steps: int                                           # model calls so far
    tool_log: Annotated[list[dict], operator.add]        # one entry per tool call


# --- tool node ------------------------------------------------------------

def _text(content) -> str:
    # flatten - mcp results arrive as a list of text blocks; the model gets one string
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)


def _result_status(text: str, is_error: bool) -> str:
    # classify - "error" for mcp errors, else the capability's own status field
    if is_error:
        return "error"
    try:
        return json.loads(text).get("status", "unknown")
    except (json.JSONDecodeError, AttributeError):
        return "unknown"


async def _run_tool(by_name: dict[str, BaseTool], call: dict, step: int):
    # call - one tool, timed, with the result text passed through unchanged
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    tool = by_name.get(call["name"])
    if tool is None:
        # model mistake - a tool name that does not exist
        text, is_error = f"unknown tool '{call['name']}'", True
    else:
        # adapter returns a ToolMessage; injected 503s come back with status "error"
        reply = await tool.ainvoke({**call, "type": "tool_call"})
        text, is_error = _text(reply.content), reply.status == "error"
    entry = {
        "step": step,
        "tool": call["name"],
        "args": call["args"],
        "result": text,
        "is_error": is_error,
        "result_status": _result_status(text, is_error),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "timestamp": started,
    }
    message = ToolMessage(content=text, tool_call_id=call["id"], name=call["name"],
                          status="error" if is_error else "success")
    return message, entry


# --- graph ----------------------------------------------------------------

def build_graph(model: BaseChatModel, tools: list[BaseTool], step_cap: int = STEP_CAP):
    bound = model.bind_tools(tools)
    by_name = {t.name: t for t in tools}

    async def agent_node(state: AgentState) -> dict:
        # think - one model call per step
        reply = await bound.ainvoke(state["messages"])
        return {"messages": [reply], "steps": state["steps"] + 1}

    async def tool_node(state: AgentState) -> dict:
        # act - run every tool call in the last reply, in order
        messages, log = [], []
        for call in state["messages"][-1].tool_calls:
            message, entry = await _run_tool(by_name, call, state["steps"])
            messages.append(message)
            log.append(entry)
        return {"messages": messages, "tool_log": log}

    def route(state: AgentState) -> str:
        # decide - answer ends the episode; tool calls continue until the step cap
        last = state["messages"][-1]
        if not getattr(last, "tool_calls", None) or state["steps"] >= step_cap:
            return END
        return "tools"

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, ["tools", END])
    graph.add_edge("tools", "agent")
    return graph.compile()


def episode_status(state: AgentState) -> str:
    # status - still asking for tools at the end means the cap cut it off
    if getattr(state["messages"][-1], "tool_calls", None):
        return "step_cap"
    # status - no tool ever ran; every task needs one, so the answer cannot
    # come from a tool (phi-4-mini sometimes writes the call as plain text)
    if not state["tool_log"]:
        return "no_tool_call"
    return "ok"


def names_a_tool(text: str, tool_names: Sequence[str]) -> bool:
    # flag - the reply mentions a tool by name; with no_tool_call this marks a
    # call written as text rather than an answer given without trying
    return any(name in text for name in tool_names)


def token_usage(messages: list[AnyMessage]) -> tuple[int, int]:
    # sum - provider-reported tokens over every model reply
    used = [m.usage_metadata for m in messages if getattr(m, "usage_metadata", None)]
    return sum(u["input_tokens"] for u in used), sum(u["output_tokens"] for u in used)


# --- episode --------------------------------------------------------------

async def run_episode(model: BaseChatModel, connections: dict[str, dict],
                      messages: list[AnyMessage], step_cap: int = STEP_CAP) -> dict:
    """run one episode with fresh servers; connections maps server name -> stdio spec"""
    client = MultiServerMCPClient(connections)
    async with AsyncExitStack() as stack:
        # open - one persistent session per server for the whole episode, so each
        # server sees every call in order (the fault schedule counts calls in phase 3)
        tools = []
        for name in connections:
            session = await stack.enter_async_context(client.session(name))
            tools += await load_mcp_tools(session)
        graph = build_graph(model, tools, step_cap)
        state = await graph.ainvoke(
            {"messages": messages, "steps": 0, "tool_log": []},
            {"recursion_limit": 2 * step_cap + 5},
        )
    status = episode_status(state)
    tokens_in, tokens_out = token_usage(state["messages"])
    # final - graded unless the cap cut the episode off mid-request
    final_text = "" if status == "step_cap" else _text(state["messages"][-1].content)
    return {
        "status": status,
        "steps": state["steps"],
        "tool_log": state["tool_log"],
        "messages": state["messages"],
        "final_text": final_text,
        "named_tool": names_a_tool(final_text, [t.name for t in tools]),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
