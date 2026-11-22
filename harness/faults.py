# file:     harness/faults.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  seeded fault schedule - which call to which tool gets which outcome
# updated:  2026-11-22

from __future__ import annotations

import hashlib
import threading
from collections import Counter
from typing import Literal

from harness.capabilities.base import EXPLICIT_ERROR, Outcome

MODES = ("natural", "prefilled")
FLAW_TYPES = ("explicit", "silent")
FlawType = Literal["explicit", "silent"]
# natural mode - exactly FAILS_PER_BLOCK failures in every BLOCK calls, so the
# realized success rate is exactly 70% (fp2: "realized success rate of 70%")
BLOCK = 10
FAILS_PER_BLOCK = 3


def stable_hash(*parts) -> int:
    # hash - sha256, not hash(), which python salts per process
    key = "|".join(str(p) for p in parts)
    return int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)


class FaultSchedule:
    """outcome of every call, fixed in advance by the episode id"""

    def __init__(self, episode_id: str, flawed_tool: str | None = None,
                 flaw_type: FlawType | None = None, mode: str = "natural"):
        # validate - a flawed tool needs a flaw type, and the reverse
        if (flawed_tool is None) != (flaw_type is None):
            raise ValueError("give flawed_tool and flaw_type together, or neither")
        if flaw_type is not None and flaw_type not in FLAW_TYPES:
            raise ValueError(f"flaw_type must be one of {FLAW_TYPES}")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.episode_id = episode_id
        self.flawed_tool = flawed_tool
        self.flaw_type = flaw_type
        self.mode = mode
        self.calls: Counter[str] = Counter()  # calls seen so far, per tool
        self._lock = threading.Lock()         # fastmcp runs sync tools in threads

    def params(self) -> dict:
        # describe - everything needed to rebuild this schedule elsewhere
        return {"episode_id": self.episode_id, "flawed_tool": self.flawed_tool,
                "flaw_type": self.flaw_type, "mode": self.mode}

    def outcome_at(self, tool: str, index: int) -> Outcome:
        # pure - outcome of call number `index` (0-based) to `tool`
        flaw = self.flaw_type
        if tool != self.flawed_tool or flaw is None:
            return "clean"
        if self.mode == "prefilled":
            return flaw  # the flawed tool fails the same way every time
        # natural - rank the 10 slots of this block by hash; the first 3 fail
        block, slot = divmod(index, BLOCK)
        ranked = sorted(range(BLOCK), key=lambda s: stable_hash(self.episode_id, tool, block, s))
        return flaw if slot in ranked[:FAILS_PER_BLOCK] else "clean"

    def decide(self, tool: str) -> Outcome:
        # decide - the register_pair hook; called once per valid call, in order
        with self._lock:
            index = self.calls[tool]
            self.calls[tool] += 1
        return self.outcome_at(tool, index)

    def realized_success(self, tool: str, n: int = BLOCK) -> float:
        # rate - share of the first n scheduled calls that are clean (study b note)
        return sum(self.outcome_at(tool, i) == "clean" for i in range(n)) / n


def annotate_outcomes(params: dict, tool_log: list[dict]) -> int:
    """replay the schedule over a finished episode's tool log.

    adds "injected" to each entry (the outcome the server applied, or None when
    the call never reached the schedule) and returns how many entries disagree
    with what the log shows; anything above 0 means a harness bug
    """
    replay = FaultSchedule(**params)
    mismatches = 0
    for entry in tool_log:
        injected_503 = entry["is_error"] and entry["result"] == EXPLICIT_ERROR
        # reached - only valid calls consult the schedule (bad args return first)
        if entry["result_status"] == "ok" or injected_503:
            entry["injected"] = replay.decide(entry["tool"])
            mismatches += (entry["injected"] == "explicit") != injected_503
        else:
            entry["injected"] = None
    return mismatches
