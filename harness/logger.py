# file:     harness/logger.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  one jsonl record per episode, failures included
# updated:  2026-11-22

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

# required - the fields every record must carry, in this order
REQUIRED = (
    "episode_id", "task_id", "condition", "episode_type", "tool_order", "rep", "seed",
    "model", "provider", "returned_model_id", "settings", "tool_calls", "first_tool",
    "final_answer", "correct", "matches_perturbed", "steps", "tokens_in", "tokens_out",
    "cost", "wall_time", "status",
)


def make_episode_id(spec: dict) -> str:
    # id - a stable hash of everything that defines the episode
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


def returned_model_id(messages: list) -> str | None:
    # model - the id the provider says it served; more than one means it changed mid-episode
    ids = {(getattr(m, "response_metadata", None) or {}).get("model_name") for m in messages}
    return ", ".join(sorted(i for i in ids if i)) or None


def build_record(spec: dict, info: dict, result: dict | None, grade: dict | None,
                 wall_time: float, error: str | None = None, mismatches: int = 0) -> dict:
    """assemble one episode record. result and grade are None when the episode crashed."""
    tool_log = result["tool_log"] if result else []
    grade = grade or {}
    return {
        "episode_id": make_episode_id(spec),
        "task_id": spec["task_id"],
        "condition": spec["condition"],
        "episode_type": spec["episode_type"],
        "tool_order": spec["tool_order"],
        "rep": spec["rep"],
        "seed": spec["seed"],
        "model": info["model"],
        "provider": info["provider"],
        "returned_model_id": returned_model_id(result["messages"]) if result else None,
        "settings": info["settings"],
        "fault": spec["fault"],
        "tool_calls": tool_log,
        "first_tool": tool_log[0]["tool"] if tool_log else None,
        "final_text": result["final_text"] if result else "",
        "final_answer": grade.get("final_answer"),
        "expected": grade.get("expected"),
        "perturbed_answer": grade.get("perturbed"),
        "correct": bool(grade.get("correct")),
        "matches_perturbed": bool(grade.get("matches_perturbed")),
        "grade_status": grade.get("grade_status"),
        "named_tool": result["named_tool"] if result else False,
        "steps": result["steps"] if result else 0,
        "tokens_in": result["tokens_in"] if result else 0,
        "tokens_out": result["tokens_out"] if result else 0,
        # cost - local models are free; openrouter cost arrives in phase 11
        "cost": 0.0 if info["provider"] == "ollama" else None,
        "wall_time": round(wall_time, 3),
        "status": result["status"] if result and not error else "error",
        "error": error,
        "schedule_mismatches": mismatches,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }


def write_record(path: Path, record: dict) -> None:
    # append - one line per episode; the file is never rewritten
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
