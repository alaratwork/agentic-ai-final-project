# file:     tests/test_descriptions.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  fact sheets match the code; rich and poor state every fact and no quality claims
# updated:  2026-11-23

from __future__ import annotations

import asyncio
import inspect
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from fastmcp import Client

import harness.descriptions as descriptions
from harness.capabilities import CAPABILITIES
from harness.descriptions import (FACTS_DIR, STYLES, all_facts, banned_words, check,
                                  describe_pair, load_facts, render)
from harness.servers import build_server

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS = yaml.safe_load((REPO_ROOT / "data/tasks/tasks.yaml").read_text())["tasks"]
SHEETS = sorted(p.stem for p in FACTS_DIR.glob("*.yaml"))


def test_every_capability_has_a_fact_sheet():
    assert SHEETS == sorted(CAPABILITIES)


@pytest.mark.parametrize("name", SHEETS)
def test_fact_sheet_matches_the_code(name):
    cap = CAPABILITIES[name]()
    facts = load_facts(name)
    # inputs - same names, same order as the tool schema
    assert [i["name"] for i in facts["inputs"]] == list(inspect.signature(cap.signature()).parameters)
    # outputs - every field a lookup returns is described, and nothing else
    # (status is the envelope; echoed inputs are already described as arguments)
    task = next(t for t in TASKS if t["capability"] == name)
    returned = set(cap.lookup(**task["args"])) - {"status"} - {i["name"] for i in facts["inputs"]}
    assert {o["name"] for o in facts["outputs"]} == returned


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("name", SHEETS)
def test_each_style_states_every_fact_and_no_banned_word(name, style):
    text = render(name, style)
    assert [f for f in all_facts(load_facts(name)) if f not in text] == []
    assert banned_words(text) == []


@pytest.mark.parametrize("name", SHEETS)
def test_pair_passes_the_equivalence_check(name):
    # check - also covers poor at most two lines and rich longer than poor
    assert check(name) == []


def test_check_catches_a_missing_fact_and_a_banned_word(monkeypatch):
    # red - a description that drops facts and adds a quality claim must fail
    monkeypatch.setattr(descriptions, "render_facts",
                        lambda facts, style: f"{facts['purpose']} Fast and reliable.")
    problems = check("forecast")
    assert any("missing fact 'town (town name)'" in p for p in problems)
    assert any("banned word 'fast'" in p for p in problems)
    assert any("banned word 'reliable'" in p for p in problems)


def test_banned_words_match_whole_words_only():
    assert banned_words("Returns the daily forecast.") == []
    assert banned_words("A fast lookup, e.g. for towns.") == ["fast", "e.g."]


def test_poor_is_the_phase_2_to_5_one_line_text():
    # pin - the 40/40 phi-4-mini baseline was measured on exactly this text
    assert render("forecast", "poor") == (
        "Returns the daily forecast for a Verrin Coast town. Arguments: town (town name), "
        "date (YYYY-MM-DD). Returns: high_c (daily high, °C), high_f (daily high, °F), "
        "condition (sky condition), precip_pct (chance of precipitation, %). "
        "Dates 2026-12-01 to 2026-12-05.")


def test_unknown_style_is_an_error():
    with pytest.raises(ValueError):
        render("forecast", "medium")


def test_default_pair_is_equal():
    pair = describe_pair("forecast")
    assert pair["a"] == pair["b"] == render("forecast", "poor")


def test_server_shows_each_tool_its_style():
    async def listed():
        server = build_server("forecast", styles={"a": "rich", "b": "poor"})
        async with Client(server) as client:
            return {t.name: t.description for t in await client.list_tools()}
    shown = asyncio.run(listed())
    assert shown["forecast_lookup_a"] == render("forecast", "rich")
    assert shown["forecast_lookup_b"] == render("forecast", "poor")


def test_check_script_passes_and_prints_all_ten():
    run = subprocess.run([sys.executable, "scripts/check_descriptions.py"], cwd=REPO_ROOT,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout
    assert run.stdout.count("=== ") == 2 * len(CAPABILITIES)
    assert "PASSED: 10 descriptions, 0 problem(s)" in run.stdout
