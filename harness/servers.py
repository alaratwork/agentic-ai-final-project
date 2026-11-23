# file:     harness/servers.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  one fastmcp server per capability, exposing tools a and b over stdio
# updated:  2026-11-23

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fastmcp import FastMCP

from harness.capabilities import CAPABILITIES
from harness.capabilities.base import Outcome, register_pair
from harness.descriptions import EQUAL, STYLES, describe_pair
from harness.faults import FLAW_TYPES, MODES, FaultSchedule

REPO_ROOT = Path(__file__).resolve().parents[1]


def always_clean(tool_name: str) -> Outcome:
    # decide - phase 2 placeholder; phase 3 swaps in the seeded fault schedule
    return "clean"


def build_server(capability: str, styles: dict[str, str] | None = None,
                 decide=None, names: dict[str, str] | None = None) -> FastMCP:
    # build - one server holding the a/b pair for one capability;
    # styles says which tool gets the rich or poor description (default poor/poor)
    cap = CAPABILITIES[capability]()
    mcp = FastMCP(name=f"{capability}-server")
    register_pair(mcp, cap, describe_pair(capability, styles), decide or always_clean, names)
    return mcp


def stdio_connection(capability: str, fault: dict | None = None,
                     styles: dict[str, str] | None = None) -> dict:
    # connect - how a client launches this server as a subprocess;
    # fault is FaultSchedule.params() and styles the a/b description styles,
    # both passed on as command-line flags.
    # server logs are muted because the client logs every call and result,
    # and tool exceptions still reach the client as error results
    args = ["-m", "harness.servers", "--capability", capability]
    for key, value in (fault or {}).items():
        if value is not None:
            args += [f"--{key.replace('_', '-')}", str(value)]
    styles = styles or EQUAL
    args += ["--style-a", styles["a"], "--style-b", styles["b"]]
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": args,
        "cwd": str(REPO_ROOT),
        "env": {"FASTMCP_LOG_LEVEL": "CRITICAL"},
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="serve one capability's a/b tools over stdio")
    parser.add_argument("--capability", required=True, choices=sorted(CAPABILITIES))
    # fault - the episode's schedule; no flawed tool means every call is clean
    parser.add_argument("--episode-id", default="dev")
    parser.add_argument("--flawed-tool", default=None)
    parser.add_argument("--flaw-type", default=None, choices=FLAW_TYPES)
    parser.add_argument("--mode", default="natural", choices=MODES)
    # describe - which description style each tool shows
    parser.add_argument("--style-a", default=EQUAL["a"], choices=STYLES)
    parser.add_argument("--style-b", default=EQUAL["b"], choices=STYLES)
    args = parser.parse_args(argv)
    schedule = FaultSchedule(args.episode_id, args.flawed_tool, args.flaw_type, args.mode)
    styles = {"a": args.style_a, "b": args.style_b}
    # serve - stdout carries the mcp protocol, so no banner and no prints
    build_server(args.capability, styles, schedule.decide).run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
