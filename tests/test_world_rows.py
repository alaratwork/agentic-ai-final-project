# file:     tests/test_world_rows.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  every world row (not just task rows) perturbs silently, plausibly and case-blind
# updated:  2026-11-22

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness.capabilities import CAPABILITIES
from harness.capabilities.base import check_perturbation
from harness.capabilities.ferry import to_minutes

TASKS = yaml.safe_load((Path(__file__).resolve().parents[1] / "data/tasks/tasks.yaml").read_text())["tasks"]
# graded - every field any task grades, per capability
GRADED = {name: sorted({t["field"] for t in TASKS if t["capability"] == name}) for name in CAPABILITIES}
# amounts - every amount the fx tasks use, plus a small and a round one
FX_AMOUNTS = sorted({t["args"]["amount"] for t in TASKS if t["capability"] == "fx"} | {1.0, 10.0})


def world_args(name: str, world: dict) -> list[dict]:
    # enumerate - one argument set per world row
    if name == "forecast":
        return [{"town": r["town"], "date": r["date"]} for r in world["forecasts"]]
    if name == "fx":
        codes = sorted(world["currencies"])
        return [{"amount": a, "base": b, "quote": q, "date": d["date"]}
                for d in world["daily_values"] for b in codes for q in codes if b != q
                for a in FX_AMOUNTS]
    if name == "stock":
        return [{"sku": r["sku"], "warehouse": r["warehouse"]} for r in world["stock"]]
    if name == "ferry":
        return [{"route": r["route"], "date": r["date"]} for r in world["sailings"]]
    if name == "staff":
        return [{"staff_id": r["staff_id"]} for r in world["staff"]]
    raise KeyError(name)


def _flip_case(args: dict) -> dict:
    return {k: v.swapcase() if isinstance(v, str) else v for k, v in args.items()}


@pytest.mark.parametrize("name", sorted(CAPABILITIES))
def test_every_world_row_perturbs_silently_and_ignores_case(name):
    cap = CAPABILITIES[name]()
    rows = world_args(name, cap.world)
    assert rows, f"no world rows for {name}"
    for args in rows:
        for field in GRADED[name]:
            check_perturbation(cap, args, field)
        clean = cap.lookup(**args)
        assert cap.lookup(**_flip_case(args)) == clean, f"case changes the answer for {args}"


@pytest.mark.parametrize("name", sorted(CAPABILITIES))
def test_perturbations_stay_plausible(name):
    # check - a silent error must look like a real answer, not an obvious glitch
    cap = CAPABILITIES[name]()
    for args in world_args(name, cap.world):
        clean = cap.lookup(**args)
        bad = cap.perturb(args, clean)
        if name == "forecast":
            assert -2.0 <= bad["high_c"] <= 16.0
        elif name == "fx":
            assert bad["rate"] > 0 and 0.03 <= abs(bad["rate"] / clean["rate"] - 1) <= 0.5
        elif name == "stock":
            assert bad["on_hand"] >= bad["reserved"] and bad["available"] >= 0
            assert 6 <= abs(bad["on_hand"] - clean["on_hand"]) <= 25
        elif name == "ferry":
            assert 5 * 60 <= to_minutes(bad["departs"]) <= 10 * 60
            assert bad["duration_min"] == clean["duration_min"]
        elif name == "staff":
            assert bad["department"] in cap.world["departments"]
            assert bad["office"] == cap.world["departments"][bad["department"]]


# model mistakes: bad formats -> invalid_argument, unknown entities -> not_found,
# even when an explicit failure is scheduled (they never reach fault injection)
MISTAKES = [
    ("fx", {"amount": -5.0, "base": "KLD", "quote": "VRM", "date": "2026-12-01"}, "invalid_argument"),
    ("fx", {"amount": 10.0, "base": "KLD", "quote": "KLD", "date": "2026-12-01"}, "invalid_argument"),
    ("fx", {"amount": 10.0, "base": "KLDR", "quote": "VRM", "date": "2026-12-01"}, "invalid_argument"),
    ("fx", {"amount": 10.0, "base": "KLD", "quote": "VRM", "date": "Dec 1"}, "invalid_argument"),
    ("fx", {"amount": 10.0, "base": "USD", "quote": "VRM", "date": "2026-12-01"}, "not_found"),
    ("fx", {"amount": 10.0, "base": "KLD", "quote": "VRM", "date": "2026-12-09"}, "not_found"),
    ("stock", {"sku": "VC1001", "warehouse": "BRN"}, "invalid_argument"),
    ("stock", {"sku": "VC-1001", "warehouse": "BR"}, "invalid_argument"),
    ("stock", {"sku": "VC-9999", "warehouse": "BRN"}, "not_found"),
    ("stock", {"sku": "VC-1001", "warehouse": "XYZ"}, "not_found"),
    ("ferry", {"route": "BRNKLS", "date": "2026-12-01"}, "invalid_argument"),
    ("ferry", {"route": "BRN-KLS", "date": "12/01/2026"}, "invalid_argument"),
    ("ferry", {"route": "BRN-OST", "date": "2026-12-01"}, "not_found"),
    ("ferry", {"route": "BRN-KLS", "date": "2026-12-09"}, "not_found"),
    ("staff", {"staff_id": "1004"}, "invalid_argument"),
    ("staff", {"staff_id": "S10045"}, "invalid_argument"),
    ("staff", {"staff_id": "S9999"}, "not_found"),
]


@pytest.mark.parametrize("name, args, status", MISTAKES)
def test_model_mistakes_are_not_faults(name, args, status):
    cap = CAPABILITIES[name]()
    assert cap.serve("explicit", **args)["status"] == status
    assert cap.serve("silent", **args)["status"] == status
