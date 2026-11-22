# file:     tests/test_descriptions.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  fact sheets match the code, and descriptions state every fact and no quality claims
# updated:  2026-11-22

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
import yaml

from harness.capabilities import CAPABILITIES
from harness.descriptions import FACTS_DIR, load_facts, render_neutral
from harness.servers import placeholder_descriptions

TASKS = yaml.safe_load((Path(__file__).resolve().parents[1] / "data/tasks/tasks.yaml").read_text())["tasks"]
SHEETS = sorted(p.stem for p in FACTS_DIR.glob("*.yaml"))
# banned - quality, speed and endorsement words (fp2 4.5; phase 6 plan)
BANNED = ("fast", "accurate", "reliable", "best", "recommended", "trusted",
          "official", "precise", "quality", "robust")


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


@pytest.mark.parametrize("name", SHEETS)
def test_neutral_description_states_every_fact_and_no_quality_claims(name):
    facts = load_facts(name)
    text = render_neutral(facts)
    every = [facts["purpose"], *(i["fact"] for i in facts["inputs"]),
             *(o["fact"] for o in facts["outputs"]), *facts.get("scope", [])]
    assert all(fact in text for fact in every)
    assert not [w for w in BANNED if re.search(rf"\b{w}\b", text, re.IGNORECASE)]


def test_server_uses_the_fact_sheet_for_both_tools():
    cap = CAPABILITIES["forecast"]()
    descriptions = placeholder_descriptions(cap)
    assert descriptions["a"] == descriptions["b"] == render_neutral(load_facts("forecast"))
    assert "high_f (daily high, °F)" in descriptions["a"]
