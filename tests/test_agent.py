# file:     tests/test_agent.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  the agent loop stops at the step cap, logs tool calls, and ends on an answer
# updated:  2026-11-22

from __future__ import annotations

import asyncio

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from harness.agent import STEP_CAP, build_graph, episode_status, names_a_tool


@tool
def echo(x: int) -> str:
    """return x as text"""
    return str(x)


class ScriptedModel(BaseChatModel):
    """fake model: asks for `tool_name` until `calls` replies, then answers"""
    tool_name: str = "echo"
    calls: int = 1000

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        replies = sum(isinstance(m, AIMessage) for m in messages)
        if replies < self.calls:
            msg = AIMessage(content="", tool_calls=[
                {"name": self.tool_name, "args": {"x": replies}, "id": f"c{replies}", "type": "tool_call"}])
        else:
            msg = AIMessage(content="done\nFINAL: 7")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def _run(model):
    graph = build_graph(model, [echo])
    start = {"messages": [HumanMessage("go")], "steps": 0, "tool_log": []}
    return asyncio.run(graph.ainvoke(start, {"recursion_limit": 2 * STEP_CAP + 5}))


def test_step_cap_stops_a_model_that_never_answers():
    state = _run(ScriptedModel())
    assert state["steps"] == STEP_CAP
    # check - tools ran after steps 1..9; the 10th request is cut off, not run
    assert len(state["tool_log"]) == STEP_CAP - 1
    assert episode_status(state) == "step_cap"


def test_answer_ends_episode_and_tool_calls_are_logged():
    state = _run(ScriptedModel(calls=2))
    assert state["steps"] == 3 and episode_status(state) == "ok"
    first = state["tool_log"][0]
    assert first["tool"] == "echo" and first["args"] == {"x": 0} and first["result"] == "0"
    assert not first["is_error"] and first["latency_ms"] >= 0 and first["timestamp"]


class TextCallModel(ScriptedModel):
    """fake model: writes the tool call as plain text instead of a real call"""
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        msg = AIMessage(content='{ "name": "echo", "arguments": {"x": 1} }\nFINAL: 7')
        return ChatResult(generations=[ChatGeneration(message=msg)])


def test_episode_where_no_tool_ran_is_flagged():
    # check - a call written as text runs nothing, so the status says so
    state = _run(TextCallModel())
    assert state["tool_log"] == [] and episode_status(state) == "no_tool_call"
    # check - every text shape phi-4-mini produced still names the tool
    for reply in ['{ "name": "echo", "arguments": {"x": 1} }', "echo(1)",
                  '{echo: {"x": 1}}', 'echo{"x": 1}']:
        assert names_a_tool(reply, ["echo"])
    # check - an answer given without trying names no tool
    assert not names_a_tool("FINAL: 7", ["echo"])


def test_unknown_tool_is_logged_as_model_mistake():
    state = _run(ScriptedModel(tool_name="no_such_tool", calls=1))
    entry = state["tool_log"][0]
    assert entry["is_error"] and entry["result"] == "unknown tool 'no_such_tool'"
    assert episode_status(state) == "ok"
