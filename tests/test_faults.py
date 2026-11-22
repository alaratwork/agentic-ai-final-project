# file:     tests/test_faults.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  the fault schedule is repeatable, hits its rates, and replays exactly
# updated:  2026-11-22

from __future__ import annotations

import pytest

from harness.capabilities.base import EXPLICIT_ERROR
from harness.faults import BLOCK, FaultSchedule, annotate_outcomes

A, B = "forecast_lookup_a", "forecast_lookup_b"


def _sequence(schedule, tool, n):
    return [schedule.decide(tool) for _ in range(n)]


def test_same_episode_gives_identical_outcomes():
    first = _sequence(FaultSchedule("ep-1", B, "explicit"), B, 200)
    again = _sequence(FaultSchedule("ep-1", B, "explicit"), B, 200)
    assert first == again


def test_different_episodes_get_different_schedules():
    runs = {tuple(_sequence(FaultSchedule(f"ep-{i}", B, "silent"), B, 20)) for i in range(20)}
    assert len(runs) > 10


def test_natural_mode_fails_exactly_three_in_every_ten_calls():
    outcomes = _sequence(FaultSchedule("ep-2", B, "explicit"), B, 1000)
    for start in range(0, 1000, BLOCK):
        assert outcomes[start:start + BLOCK].count("explicit") == 3
    assert outcomes.count("clean") / 1000 == pytest.approx(0.70)


def test_first_call_fails_about_thirty_percent_of_episodes():
    firsts = [FaultSchedule(f"ep-{i}", B, "silent").decide(B) for i in range(2000)]
    assert 0.26 < firsts.count("silent") / 2000 < 0.34


def test_prefilled_mode_always_fails_the_same_way():
    assert set(_sequence(FaultSchedule("ep-3", A, "silent", "prefilled"), A, 50)) == {"silent"}


def test_unflawed_tool_and_clean_episodes_are_always_clean():
    schedule = FaultSchedule("ep-4", B, "explicit")
    assert set(_sequence(schedule, A, 100)) == {"clean"}
    assert set(_sequence(FaultSchedule("ep-5"), B, 100)) == {"clean"}


def test_calls_are_counted_per_tool():
    # check - calls to a must not shift b's schedule
    plain = _sequence(FaultSchedule("ep-6", B, "explicit"), B, 30)
    mixed = FaultSchedule("ep-6", B, "explicit")
    interleaved = []
    for _ in range(30):
        mixed.decide(A)
        interleaved.append(mixed.decide(B))
    assert interleaved == plain


def test_realized_success_for_the_study_b_note():
    schedule = FaultSchedule("ep-7", B, "explicit")
    assert schedule.realized_success(B) == 0.7 and schedule.realized_success(A) == 1.0
    assert FaultSchedule("ep-7", B, "explicit", "prefilled").realized_success(B) == 0.0


@pytest.mark.parametrize("kwargs", [
    {"flawed_tool": B}, {"flaw_type": "silent"},
    {"flawed_tool": B, "flaw_type": "loud"}, {"mode": "sometimes"},
])
def test_bad_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        FaultSchedule("ep-8", **kwargs)


def _entry(tool, status="ok", error=False, result="{}"):
    return {"tool": tool, "result_status": "error" if error else status,
            "is_error": error, "result": result}


def test_replay_labels_each_call_and_skips_model_mistakes():
    params = FaultSchedule("ep-9", A, "explicit", "prefilled").params()
    log = [_entry(A, status="invalid_argument"),          # bad args: never reached
           _entry(A, error=True, result=EXPLICIT_ERROR),  # injected 503
           _entry(B)]                                     # clean call to the other tool
    assert annotate_outcomes(params, log) == 0
    assert [e["injected"] for e in log] == [None, "explicit", "clean"]


def test_replay_detects_a_log_that_disagrees_with_the_schedule():
    params = FaultSchedule("ep-9", A, "explicit", "prefilled").params()
    assert annotate_outcomes(params, [_entry(A)]) == 1  # schedule says 503, log says ok
