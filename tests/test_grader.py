# file:     tests/test_grader.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  the grader reads the FINAL line the way a careful human would
# updated:  2026-11-22

from __future__ import annotations

import json as _json

import pytest

from harness.capabilities import CAPABILITIES
from harness.capabilities.base import DATA_DIR, Capability, ok
from harness.grader import extract_final, grade, grade_values, to_answer, to_answers

FC01 = ({"town": "Brennick", "date": "2026-12-01"}, "high_c")   # clean 5.60, perturbed 9.10
FC06 = ({"town": "Wexmoor", "date": "2026-12-01"}, "high_f")    # clean 43.00


@pytest.fixture(scope="module")
def forecast():
    return CAPABILITIES["forecast"]()


# --- correct answers in the shapes models actually write -----------------

@pytest.mark.parametrize("reply", [
    "FINAL: 5.6",
    "FINAL: 5.6°C",
    "FINAL: 5.6 °C",
    "final: 5.60",
    "FINAL: 5.6.",
    "Let me think.\nFINAL: 9.1\nActually, rechecking.\nFINAL: 5.6",
    "**FINAL: 5.6**",
    "FINAL: **5.6**",
    "**FINAL:** 5.6",
    "FINAL: `5.6`",
    "FINAL: 5.6 degrees",
    "FINAL: 5.6 degrees C",
    "FINAL: 5.6 C",
    "FINAL: 5.6 celsius",
    "> FINAL: 5.6",
])
def test_correct_answer_shapes_are_accepted(forecast, reply):
    g = grade(reply, forecast, *FC01)
    assert g["grade_status"] == "graded" and g["correct"], g


@pytest.mark.parametrize("reply", ["FINAL: 43°F", "FINAL: 43", "FINAL: 43.0 °F", "FINAL: 43 fahrenheit"])
def test_fahrenheit_field_fc06(forecast, reply):
    assert grade(reply, forecast, *FC06)["correct"]


# --- wrong or missing answers stay wrong ----------------------------------

@pytest.mark.parametrize("reply", ["FINAL: 9.1", "FINAL: approximately 5.6", "FINAL: 5.6 to 6.0"])
def test_wrong_or_hedged_answers_are_not_correct(forecast, reply):
    assert not grade(reply, forecast, *FC01)["correct"]


@pytest.mark.parametrize("reply", ["The answer is 5.6", "", "FINAL 5.6", "final answer: 5.6"])
def test_missing_final_line(forecast, reply):
    g = grade(reply, forecast, *FC01)
    assert g["grade_status"] == "no_final_answer" and not g["correct"]


def test_perturbed_answer_is_flagged(forecast):
    g = grade("FINAL: 9.1", forecast, *FC01)
    assert g["matches_perturbed"] and not g["correct"]


# --- other answer types (capabilities not built yet, so test to_answer) ----

@pytest.mark.parametrize("raw, expected", [
    ("1,919.04 OSK", "1919.04"),     # fx: thousands separator + currency code
    ("1919.04", "1919.04"),
    ("**1,919.04** OSK", "1919.04"),
    ("12 units", "12.00"),           # stock: count with a unit word
    ("08:35", "08:35"),              # ferry: clock time
    ("8:35", "08:35"),               # same time without the leading zero
    ("Customs", "customs"),          # staff: department
    ("**Kelsholm**.", "kelsholm"),   # staff: office town, decorated
    ('"Kelsholm"', "kelsholm"),
    ("-2.5", "-2.50"),
])
def test_to_answer_normalizes_like_the_oracle(raw, expected):
    assert to_answer(raw) == expected


def test_extract_final_takes_the_last_line():
    assert extract_final("FINAL: 1\nFINAL: 2") == "2"
    assert extract_final("no answer here") is None


# --- multi-value answers (parallel tasks, phase 12) -----------------------



def test_semicolon_answers_are_split_and_normalized():
    assert to_answers("5.6; 7.3") == ["5.60", "7.30"]
    assert to_answers("5.6°C;7.3 °C;") == ["5.60", "7.30"]   # trailing separator tolerated
    assert to_answers("1,919.04 OSK") == ["1919.04"]          # commas are not separators


@pytest.mark.parametrize("reply, correct", [
    ("FINAL: 5.6; 7.3", True),
    ("FINAL: **5.6; 7.3**", True),
    ("FINAL: 7.3; 5.6", False),       # element by element, in the order asked
    ("FINAL: 5.6; 9.9", False),       # one value wrong
    ("FINAL: 5.6", False),            # one value missing
    ("FINAL: 5.6; 7.3; 1.0", False),  # one value extra
])
def test_multi_value_answers_compare_element_by_element(reply, correct):
    g = grade_values(reply, expected=["5.60", "7.30"], perturbed=["9.10", "7.30"])
    assert g["correct"] is correct and g["grade_status"] == "graded"


def test_multi_value_perturbed_and_missing():
    assert grade_values("FINAL: 9.1; 7.3", ["5.60", "7.30"], ["9.10", "7.30"])["matches_perturbed"]
    assert grade_values("no answer", ["5.60", "7.30"], ["9.10", "7.30"])["grade_status"] == "no_final_answer"


# --- fx-02: the fx capability lands in phase 5 ------------------




class FxStandIn(Capability):
    """stand-in until phase 5: the design-doc formula over the real fx.json"""
    name, tool_stem = "fx", "fx_convert"

    def signature(self):
        def fx_convert(amount: float, base: str, quote: str, date: str) -> dict:
            """schema stub only"""
        return fx_convert

    def lookup(self, amount, base, quote, date):
        world = _json.loads((DATA_DIR / "world" / "fx.json").read_text())
        values = next(d["values"] for d in world["daily_values"] if d["date"] == date)
        rate = round(values[base] / values[quote], 4)
        return ok(base=base, quote=quote, date=date, amount=amount, rate=rate,
                  converted=round(amount * rate, 2))

    def perturb(self, args, result):
        rate = round(result["rate"] * 1.06, 4)
        return {**result, "rate": rate, "converted": round(result["amount"] * rate, 2)}


FX02 = ({"amount": 1200.0, "base": "VRM", "quote": "OSK", "date": "2026-12-02"}, "converted")


def test_fx02_accepts_thousands_separator_and_currency_code():
    g = grade("FINAL: 1,919.04 OSK", FxStandIn(world={}), *FX02)
    assert g["expected"] == "1919.04" and g["correct"]


def test_fx02_with_the_real_fx_capability():
    if "fx" not in CAPABILITIES:
        pytest.skip("fx capability lands in phase 5")
    assert grade("FINAL: 1,919.04 OSK", CAPABILITIES["fx"](), *FX02)["correct"]
