# file:     harness/descriptions.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  render rich and poor tool descriptions from one fact sheet, and check them
# updated:  2026-11-23

# the description is the manipulated variable (fp2 4.5). both styles come from
# the same fact sheet, so they carry the same facts and differ only in
# presentation; check() enforces that before any episode runs.

from __future__ import annotations

import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from harness.capabilities.base import DATA_DIR

FACTS_DIR = DATA_DIR / "facts"
TEMPLATES_DIR = DATA_DIR / "templates"
STYLES = ("rich", "poor")
EQUAL = {"a": "poor", "b": "poor"}  # default pairing: no description difference
POOR_MAX_LINES = 2

# banned - quality, speed and endorsement words from the phase 6 plan (first row),
# then status cues that would hint which tool is better, then example markers
BANNED = (
    "fast", "accurate", "reliable", "best", "recommended", "trusted",
    "official", "precise", "quality", "robust",
    "always", "guaranteed", "authoritative", "verified", "validated", "up-to-date",
    "latest", "real-time", "live", "comprehensive", "complete", "detailed", "exact",
    "efficient", "quick", "instant", "dependable", "consistent", "stable",
    "preferred", "primary", "premium", "improved", "legacy", "deprecated", "backup",
    "fallback",
    "example", "examples", "e.g.", "for instance", "such as",
)

# render - strict: a missing fact-sheet key is an error, not a blank
_ENV = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True,
                   lstrip_blocks=True, undefined=StrictUndefined, autoescape=False)


def facts_path(capability: str) -> Path:
    return FACTS_DIR / f"{capability}.yaml"


def load_facts(capability: str) -> dict:
    return yaml.safe_load(facts_path(capability).read_text())


def all_facts(facts: dict) -> list[str]:
    # list - every string that both styles must contain verbatim
    return [facts["purpose"], *(i["fact"] for i in facts["inputs"]),
            *(o["fact"] for o in facts["outputs"]), *facts.get("scope", [])]


def render_facts(facts: dict, style: str) -> str:
    if style not in STYLES:
        raise ValueError(f"unknown description style '{style}', expected one of {STYLES}")
    data = {"scope": [], **facts}
    return _ENV.get_template(f"{style}.j2").render(**data).strip()


def render(capability: str, style: str) -> str:
    return render_facts(load_facts(capability), style)


def describe_pair(capability: str, styles: dict[str, str] | None = None) -> dict[str, str]:
    # pair - {"a": text, "b": text}, the shape register_pair expects
    styles = styles or EQUAL
    return {key: render(capability, styles[key]) for key in ("a", "b")}


def banned_words(text: str) -> list[str]:
    # match - whole words only, so "forecast" never trips "fast"
    return [w for w in BANNED
            if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text, re.IGNORECASE)]


def check(capability: str) -> list[str]:
    # check - every fact in both styles, no banned words, poor stays terse,
    # rich is the longer one; returns problems, empty means pass
    facts = load_facts(capability)
    texts = {style: render_facts(facts, style) for style in STYLES}
    problems = []
    for style, text in texts.items():
        problems += [f"{capability}/{style}: missing fact {f!r}" for f in all_facts(facts) if f not in text]
        problems += [f"{capability}/{style}: banned word {w!r}" for w in banned_words(text)]
    if len(texts["poor"].splitlines()) > POOR_MAX_LINES:
        problems.append(f"{capability}/poor: more than {POOR_MAX_LINES} lines")
    if len(texts["rich"].split()) <= len(texts["poor"].split()):
        problems.append(f"{capability}/rich: not longer than poor")
    return problems
