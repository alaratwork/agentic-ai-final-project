# file:     harness/descriptions.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  load a capability's fact sheet and render tool descriptions from it
# updated:  2026-11-22

# now: one neutral description, shared by a and b
# phase 6: rich and poor renderings from the same facts (jinja templates)

from __future__ import annotations

from pathlib import Path

import yaml

from harness.capabilities.base import DATA_DIR

FACTS_DIR = DATA_DIR / "facts"


def facts_path(capability: str) -> Path:
    return FACTS_DIR / f"{capability}.yaml"


def load_facts(capability: str) -> dict | None:
    # load - None when the fact sheet is not written yet
    path = facts_path(capability)
    return yaml.safe_load(path.read_text()) if path.exists() else None


def render_neutral(facts: dict) -> str:
    # render - purpose, arguments, returned fields with units, scope limits
    inputs = ", ".join(i["fact"] for i in facts["inputs"])
    outputs = ", ".join(o["fact"] for o in facts["outputs"])
    scope = " ".join(facts.get("scope", []))
    return f"{facts['purpose']} Arguments: {inputs}. Returns: {outputs}. {scope}".strip()
