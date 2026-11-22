# file:     harness/capabilities/base.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   alara hakki
# purpose:  shared contract every capability follows
# updated:  2026-11-22 (archit gupta: _make_handler validates before decide)

from __future__ import annotations

import functools
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Literal

Outcome = Literal["clean", "explicit", "silent"]

# one injected error string, identical across all five capabilities
EXPLICIT_ERROR = "503 Service Unavailable: upstream timeout"

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class InjectedFailure(Exception):
    """scheduled explicit error; surfaces to the agent as an mcp tool error"""


# --- result shapes -------------------------------------------------------
# injected failures are mcp errors; model mistakes are normal results with
# their own status, so the two never look alike in logs or to the agent

def ok(**fields) -> dict:
    return {"status": "ok", **fields}


def not_found(message: str) -> dict:
    return {"status": "not_found", "message": message}


def invalid(message: str) -> dict:
    return {"status": "invalid_argument", "message": message}


def normalize(value) -> str:
    # normalize - numbers to two decimals, text lowercase and trimmed
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    return str(value).strip().lower().rstrip(".")


# --- capability contract -------------------------------------------------

class Capability(ABC):
    """one capability = one world file, one pure lookup, one perturbation"""

    name: str        # matches data/world/<name>.json and data/facts/<name>.yaml
    tool_stem: str   # default tool names are <tool_stem>_a and <tool_stem>_b

    def __init__(self, world: dict | None = None):
        # load - world data from disk unless a test passes its own
        if world is None:
            path = DATA_DIR / "world" / f"{self.name}.json"
            world = json.loads(path.read_text())
        self.world = world

    @abstractmethod
    def signature(self) -> Callable:
        """typed stub; its parameters become the tool schema for a and b"""

    @abstractmethod
    def lookup(self, **args) -> dict:
        """pure function over self.world; returns ok, not_found or invalid"""

    @abstractmethod
    def perturb(self, args: dict, result: dict) -> dict:
        """deterministic, plausible, internally consistent wrong result"""

    def answer(self, result: dict, field: str) -> str:
        # extract - the graded value from one result field
        return normalize(result[field])

    def serve(self, outcome: Outcome, **args) -> dict:
        # lookup - model mistakes return before any fault is applied
        result = self.lookup(**args)
        if result["status"] != "ok":
            return result
        # apply - the scheduled outcome
        if outcome == "explicit":
            raise InjectedFailure(EXPLICIT_ERROR)
        if outcome == "silent":
            return self.perturb(args, result)
        return result


# --- checks shared by every capability's tests --------------------------

def check_perturbation(cap: Capability, args: dict, field: str) -> None:
    # check - same fields, same types, still ok, different graded answer
    clean = cap.lookup(**args)
    assert clean["status"] == "ok", f"{args} has no clean answer"
    bad = cap.perturb(args, clean)
    assert set(bad) == set(clean), f"perturbation changed fields for {args}"
    for key in clean:
        assert type(bad[key]) is type(clean[key]), f"{key} changed type for {args}"
    assert bad["status"] == "ok", f"perturbation is not silent for {args}"
    assert cap.answer(bad, field) != cap.answer(clean, field), (
        f"perturbation leaves {field} unchanged for {args}")
    assert cap.perturb(args, clean) == bad, f"perturbation not deterministic for {args}"


# --- mcp registration ----------------------------------------------------

def _make_handler(cap, stub, tool_name, decide, tool_error):
    # wrap - copy the stub signature so a and b get identical schemas
    @functools.wraps(stub)
    def handler(**kwargs):
        # validate - model mistakes return before decide() is asked, so they
        # never use up a scheduled outcome (changed 2026-11-22, archit gupta,
        # see docs/progress.md)
        checked = cap.lookup(**kwargs)
        if checked["status"] != "ok":
            return checked
        try:
            return cap.serve(decide(tool_name), **kwargs)
        except InjectedFailure as exc:
            raise tool_error(str(exc)) from None
    handler.__name__ = tool_name
    return handler


def register_pair(mcp, cap: Capability, descriptions: dict[str, str],
                  decide: Callable[[str], Outcome],
                  names: dict[str, str] | None = None) -> None:
    """register tools a and b on a fastmcp server.

    descriptions: {"a": text, "b": text}, rendered from the fact sheet
    decide:       fault-injector hook, tool name -> outcome for this call
    names:        neutral names from config; defaults to <stem>_a / <stem>_b
    """
    from fastmcp.exceptions import ToolError  # import - only when serving

    names = names or {"a": f"{cap.tool_stem}_a", "b": f"{cap.tool_stem}_b"}
    stub = cap.signature()
    for key in ("a", "b"):
        handler = _make_handler(cap, stub, names[key], decide, ToolError)
        mcp.tool(name=names[key], description=descriptions[key])(handler)
