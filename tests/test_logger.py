# file:     tests/test_logger.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  episode records carry every required field, and failures are kept
# updated:  2026-11-22

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from harness.logger import REQUIRED, build_record, make_episode_id, read_records, write_record

SPEC = {"task_id": "fc-01", "condition": "dev", "episode_type": "natural", "tool_order": "ab",
        "rep": 0, "seed": 0, "model": "phi4-mini",
        "fault": {"episode_id": "x", "flawed_tool": None, "flaw_type": None, "mode": "natural"}}
INFO = {"model": "phi4-mini", "provider": "ollama", "settings": {"temperature": 0.5, "top_p": 1.0}}
CALL = {"step": 1, "tool": "forecast_lookup_a", "args": {"town": "Brennick", "date": "2026-12-01"},
        "result": '{"status":"ok"}', "is_error": False, "result_status": "ok",
        "latency_ms": 5.0, "timestamp": "t", "injected": "clean"}
RESULT = {"status": "ok", "steps": 2, "tool_log": [CALL], "final_text": "FINAL: 5.6",
          "named_tool": False, "tokens_in": 460, "tokens_out": 65,
          "messages": [HumanMessage("q"), AIMessage("FINAL: 5.6", response_metadata={"model_name": "phi4-mini-tools:latest"})]}
GRADE = {"final_answer": "5.60", "expected": "5.60", "perturbed": "9.10",
         "correct": True, "matches_perturbed": False, "grade_status": "graded"}


def test_record_has_every_required_field_and_survives_jsonl(tmp_path):
    record = build_record(SPEC, INFO, RESULT, GRADE, wall_time=4.0)
    assert [k for k in REQUIRED if k not in record] == []
    assert record["first_tool"] == "forecast_lookup_a" and record["correct"]
    assert record["returned_model_id"] == "phi4-mini-tools:latest" and record["cost"] == 0.0
    path = tmp_path / "episodes.jsonl"
    write_record(path, record)
    write_record(path, record)
    assert read_records(path) == [record, record]


def test_a_crashed_episode_is_still_a_record(tmp_path):
    record = build_record(SPEC, INFO, None, None, wall_time=0.5, error="ConnectionError: refused")
    assert [k for k in REQUIRED if k not in record] == []
    assert record["status"] == "error" and record["error"].startswith("ConnectionError")
    assert record["tool_calls"] == [] and record["first_tool"] is None and not record["correct"]
    write_record(tmp_path / "e.jsonl", record)
    assert read_records(tmp_path / "e.jsonl")[0]["status"] == "error"


def test_episode_id_is_stable_and_ignores_key_order():
    assert make_episode_id({"a": 1, "b": 2}) == make_episode_id({"b": 2, "a": 1})
    assert make_episode_id(SPEC) != make_episode_id({**SPEC, "seed": 1})
