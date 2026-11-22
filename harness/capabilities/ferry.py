# file:     harness/capabilities/ferry.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  ferry capability - first sailing of the day on a directional route
# updated:  2026-11-22

from __future__ import annotations

import re

from .base import Capability, invalid, not_found, ok, stable_int

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ROUTE_RE = re.compile(r"^[A-Za-z]{3}-[A-Za-z]{3}$")

# departure shifts in minutes - 20 to 50 in 5-minute steps (capability_design.md)
SHIFTS = (20, 25, 30, 35, 40, 45, 50)
PLAUSIBLE = (5 * 60, 10 * 60)  # perturbed departures stay within 05:00 to 10:00


def to_minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def to_clock(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class FerryCapability(Capability):
    name = "ferry"
    tool_stem = "ferry_schedule"

    def signature(self):
        # define - parameter names and types are the tool schema
        def ferry_schedule(route: str, date: str) -> dict:
            """schema stub only; never called"""
        return ferry_schedule

    def lookup(self, route: str, date: str) -> dict:
        # validate - bad formats are model mistakes, never faults
        if not isinstance(route, str) or not ROUTE_RE.match(route.strip()):
            return invalid("route must be two three-letter port codes joined by a hyphen")
        if not isinstance(date, str) or not DATE_RE.match(date.strip()):
            return invalid("date must be YYYY-MM-DD, e.g. '2026-12-01'")
        # match - case-insensitive, identical for a and b; direction matters
        key, day = route.strip().upper(), date.strip()
        rows = [e for e in self.world["sailings"] if e["route"] == key]
        if not rows:
            return not_found(f"no ferry route '{key}'")
        entry = next((e for e in rows if e["date"] == day), None)
        if entry is None:
            return not_found(f"no sailing on '{key}' on {day}")
        # derive - arrival from departure plus crossing time; cast so types never drift
        departs, duration = entry["first_departure"], int(entry["duration_min"])
        return ok(route=key, date=day, departs=departs,
                  arrives=to_clock(to_minutes(departs) + duration), duration_min=duration)

    def perturb(self, args: dict, result: dict) -> dict:
        # seed - from the canonical result, so 'brn-kls' and 'BRN-KLS' agree
        seed = stable_int(self.name, result["route"], result["date"])
        delta = SHIFTS[seed % len(SHIFTS)]
        sign = 1 if (seed >> 8) % 2 else -1
        # shift - flip direction if the first choice leaves the 05:00-10:00 window
        departs = to_minutes(result["departs"]) + sign * delta
        if not PLAUSIBLE[0] <= departs <= PLAUSIBLE[1]:
            departs = to_minutes(result["departs"]) - sign * delta
        # recompute - arrival follows the perturbed departure; crossing time unchanged
        return {**result, "departs": to_clock(departs),
                "arrives": to_clock(departs + result["duration_min"])}
