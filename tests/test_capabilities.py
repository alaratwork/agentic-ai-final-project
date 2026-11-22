# file:     tests/test_capabilities.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   alara hakki
# purpose:  every task has a clean answer and a silent, deterministic perturbation
# updated:  2026-11-22 (archit gupta: uses the shared capability registry)

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.capabilities import CAPABILITIES
from harness.capabilities.base import (EXPLICIT_ERROR, InjectedFailure,
                                       check_perturbation)
from harness.capabilities.forecast import ForecastCapability

TASKS_PATH = Path(__file__).resolve().parents[1] / "data" / "tasks" / "tasks.yaml"
TASKS = yaml.safe_load(TASKS_PATH.read_text())["tasks"]

# register - the shared registry in harness/capabilities/__init__.py
# (changed 2026-11-22, archit gupta: was a local dict)


def _cases():
    # skip - tasks whose capability is not written yet
    for task in TASKS:
        marks = () if task["capability"] in CAPABILITIES else (
            pytest.mark.skip(reason=f"{task['capability']} not implemented"),)
        yield pytest.param(task, id=task["id"], marks=marks)


def _flip_case(args: dict) -> dict:
    # vary - same call, different casing
    return {k: v.swapcase() if isinstance(v, str) else v for k, v in args.items()}


@pytest.mark.parametrize("task", list(_cases()))
def test_task_perturbs_silently(task):
    cap = CAPABILITIES[task["capability"]]()
    check_perturbation(cap, task["args"], task["field"])


@pytest.mark.parametrize("task", list(_cases()))
def test_matching_ignores_case(task):
    cap = CAPABILITIES[task["capability"]]()
    clean = cap.lookup(**task["args"])
    flipped = cap.lookup(**_flip_case(task["args"]))
    assert flipped == clean
    assert cap.perturb(task["args"], flipped) == cap.perturb(task["args"], clean)


@pytest.mark.parametrize("task", list(_cases()))
def test_serve_applies_each_outcome(task):
    cap = CAPABILITIES[task["capability"]]()
    assert cap.serve("clean", **task["args"]) == cap.lookup(**task["args"])
    with pytest.raises(InjectedFailure, match=EXPLICIT_ERROR):
        cap.serve("explicit", **task["args"])
    assert cap.serve("silent", **task["args"])["status"] == "ok"


def test_model_mistakes_are_not_faults():
    # check - bad args never reach fault injection, even when explicit is scheduled
    cap = ForecastCapability()
    assert cap.serve("explicit", town="Brennick", date="Dec 1")["status"] == "invalid_argument"
    assert cap.serve("silent", town="Atlantis", date="2026-12-01")["status"] == "not_found"
    assert cap.serve("explicit", town="Brennick", date="2026-12-09")["status"] == "not_found"
