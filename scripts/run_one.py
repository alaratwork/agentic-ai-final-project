# file:     scripts/run_one.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  run one task end to end on one model, grade it, and log the record (debug tool)
# updated:  2026-11-23

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage

# path - make `harness` importable when run as `python scripts/run_one.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from harness.agent import run_episode  # noqa: E402
from harness.capabilities import CAPABILITIES  # noqa: E402
from harness.descriptions import EQUAL, STYLES  # noqa: E402
from harness.faults import FLAW_TYPES, MODES, FaultSchedule, annotate_outcomes  # noqa: E402
from harness.grader import grade  # noqa: E402
from harness.logger import build_record, make_episode_id, write_record  # noqa: E402
from harness.models import MODELS, get_chat_model, model_info  # noqa: E402
from harness.servers import stdio_connection  # noqa: E402

TASKS_PATH = REPO_ROOT / "data" / "tasks" / "tasks.yaml"
DEFAULT_OUT = REPO_ROOT / "results" / "dev" / "episodes.jsonl"


def load_task(task_id: str) -> tuple[dict, str]:
    # load - one task plus the shared answer instruction
    data = yaml.safe_load(TASKS_PATH.read_text())
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if task is None:
        sys.exit(f"unknown task '{task_id}'")
    return task, data["answer_instruction"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run one task end to end and log the record")
    parser.add_argument("--task", required=True, help="task id, e.g. fc-01")
    parser.add_argument("--model", default="phi4-mini")
    parser.add_argument("--seed", type=int, default=0, help="model sampling seed")
    parser.add_argument("--flaw-tool", choices=["a", "b"], help="which tool of the pair is flawed")
    parser.add_argument("--flaw-type", choices=FLAW_TYPES)
    parser.add_argument("--mode", choices=MODES, default="natural",
                        help="natural: 3 of every 10 calls fail; prefilled: every call fails")
    parser.add_argument("--style-a", choices=STYLES, default=EQUAL["a"], help="description style of tool a")
    parser.add_argument("--style-b", choices=STYLES, default=EQUAL["b"], help="description style of tool b")
    parser.add_argument("--condition", default="dev")
    parser.add_argument("--rep", type=int, default=0)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if (args.flaw_tool is None) != (args.flaw_type is None):
        parser.error("--flaw-tool and --flaw-type go together")
    return args


def main() -> None:
    args = parse_args()
    task, instruction = load_task(args.task)
    if task["capability"] not in CAPABILITIES:
        sys.exit(f"capability '{task['capability']}' is not built yet")
    cap = CAPABILITIES[task["capability"]]()
    prompt = f"{task['prompt']}\n\n{instruction}"

    # spec - everything that defines this episode; its hash is the episode id
    flawed_tool = f"{cap.tool_stem}_{args.flaw_tool}" if args.flaw_tool else None
    styles = {"a": args.style_a, "b": args.style_b}
    spec = {"task_id": task["id"], "condition": args.condition, "episode_type": args.mode,
            "tool_order": "ab", "rep": args.rep, "seed": args.seed, "model": args.model,
            "styles": styles,
            "fault": {"flawed_tool": flawed_tool, "flaw_type": args.flaw_type, "mode": args.mode}}
    episode_id = make_episode_id(spec)
    schedule = FaultSchedule(episode_id, flawed_tool, args.flaw_type, args.mode)
    print(f"episode {episode_id} · task {task['id']} · model {args.model} · seed {args.seed}")
    print(f"descriptions: a={styles['a']} b={styles['b']}")
    print(f"fault: {flawed_tool or 'none'} {args.flaw_type or ''} ({args.mode})\n")
    print(f"PROMPT\n{prompt}\n")

    # run - fresh server subprocess holding this episode's schedule; any
    # exception becomes a record with status "error", never a lost episode
    info = {"model": args.model, "provider": MODELS.get(args.model, {}).get("backend", "unknown"),
            "settings": {}}
    result = graded = error = None
    mismatches = 0
    start = time.perf_counter()
    try:
        info = model_info(args.model)
        model = get_chat_model(args.model, seed=args.seed)
        connections = {task["capability"]: stdio_connection(task["capability"], schedule.params(), styles)}
        result = asyncio.run(run_episode(model, connections, [HumanMessage(prompt)]))
        graded = grade(result["final_text"], cap, task["args"], task["field"])
        mismatches = annotate_outcomes(schedule.params(), result["tool_log"])
    except Exception as exc:  # noqa: BLE001 - every failure is data
        error = f"{type(exc).__name__}: {exc}"
    wall = time.perf_counter() - start

    record = build_record(spec, info, result, graded, wall, error, mismatches)
    write_record(args.out, record)

    # show - what happened, call by call
    for i, call in enumerate(record["tool_calls"], 1):
        print(f"TOOL CALL {i} (step {call['step']}) {call['tool']}({json.dumps(call['args'])})"
              f"  [{call['latency_ms']} ms] injected={call.get('injected')}")
        print(f"  -> {'ERROR ' if call['is_error'] else ''}{call['result']}\n")
    if not record["tool_calls"]:
        print("(no tool calls)\n")
    print(f"FINAL REPLY\n{record['final_text'] or '(none)'}\n")
    if error:
        print(f"ERROR {error}")
    if record["status"] == "no_tool_call":
        print("note: no tool ran;", "the reply names a tool (call written as text)"
              if record["named_tool"] else "the model answered without trying a tool")
    if mismatches:
        print(f"WARNING {mismatches} tool call(s) disagree with the fault schedule (harness bug)")
    print(f"status {record['status']} · steps {record['steps']} · "
          f"tokens {record['tokens_in']} in / {record['tokens_out']} out · {record['wall_time']:.1f} s")
    print(f"answer {record['final_answer']!r} · expected {record['expected']!r} · "
          f"perturbed {record['perturbed_answer']!r} · grade {record['grade_status']}"
          f" · matches_perturbed {record['matches_perturbed']}")
    print(f"record -> {args.out.relative_to(REPO_ROOT) if args.out.is_relative_to(REPO_ROOT) else args.out}")
    print("CORRECT" if record["correct"] else "WRONG")


if __name__ == "__main__":
    main()
