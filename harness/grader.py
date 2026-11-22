# file:     harness/grader.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  read the FINAL line and compare it with the clean and perturbed answers
# updated:  2026-11-22

# grade() handles single-call tasks; grade_values() is the general comparison,
# so phase 12's parallel tasks pass lists of expected values ("FINAL: 5.6; 7.3")

from __future__ import annotations

import re

from harness.capabilities.base import Capability, normalize

# the label may carry markdown around it: **FINAL:**, > FINAL:, - FINAL:
FINAL_RE = re.compile(r"^[\s>*_`#-]*FINAL[*_`\s]*:\s*(.*?)\s*$", re.IGNORECASE | re.MULTILINE)
# units a model may write after a number: °, °C, degrees C, celsius, fahrenheit,
# C, F, units, or a three-letter currency code like OSK
UNIT = r"°\s*[CF]?|degrees?(?:\s*[CF])?|celsius|fahrenheit|units?|[A-Za-z]{3}|[CF]"
NUMBER_RE = re.compile(rf"([-+]?\d+(?:\.\d+)?)\s*(?:{UNIT})?", re.IGNORECASE)
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")


def extract_final(text: str) -> str | None:
    # find - the last line that starts with FINAL:, else None
    found = FINAL_RE.findall(text or "")
    return found[-1] if found else None


def to_answer(raw: str) -> str:
    # strip - markdown marks and quotes, then a trailing full stop
    value = re.sub(r"[*_`]", "", raw).strip().strip("\"'").strip().rstrip(".")
    # drop - thousands separators (1,919.04 -> 1919.04)
    value = re.sub(r"(?<=\d),(?=\d{3}\b)", "", value)
    # number - a number with at most one unit after it, normalized like the oracle
    number = NUMBER_RE.fullmatch(value)
    if number:
        return normalize(float(number.group(1)))
    # time - 8:35 and 08:35 are the same clock time
    time = TIME_RE.fullmatch(value)
    if time:
        return f"{int(time.group(1)):02d}:{time.group(2)}"
    # text - anything else (hedges, ranges, names) is compared as written
    return normalize(value)


def to_answers(raw: str) -> list[str]:
    # split - several values are separated by ";" (commas clash with 1,919.04);
    # an empty piece, e.g. after a trailing ";", is dropped
    return [to_answer(part) for part in raw.split(";") if part.strip(" *_`")]


def grade_values(final_text: str, expected: list[str], perturbed: list[str]) -> dict:
    """compare the FINAL line with expected values, element by element, in order.

    expected / perturbed: normalized answers from the oracle and from the
    perturbed pipeline; one element for single-value tasks
    """
    shown = {"expected": "; ".join(expected), "perturbed": "; ".join(perturbed)}
    raw = extract_final(final_text)
    if raw is None:
        return {**shown, "final_answer": None, "correct": False,
                "matches_perturbed": False, "grade_status": "no_final_answer"}
    answers = to_answers(raw)
    return {**shown, "final_answer": "; ".join(answers),
            "correct": answers == expected, "matches_perturbed": answers == perturbed,
            "grade_status": "graded"}


def grade(final_text: str, cap: Capability, args: dict, field: str) -> dict:
    # oracle - expected answers come from the world data, never stored
    clean = cap.lookup(**args)
    expected = cap.answer(clean, field)
    perturbed = cap.answer(cap.perturb(args, clean), field)
    return grade_values(final_text, [expected], [perturbed])
