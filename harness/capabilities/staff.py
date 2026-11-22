# file:     harness/capabilities/staff.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  staff capability - directory entry for a verrin coast authority staff member
# updated:  2026-11-22

from __future__ import annotations

import re

from .base import Capability, invalid, not_found, ok, stable_int

ID_RE = re.compile(r"^[Ss]\d{4}$")


class StaffCapability(Capability):
    name = "staff"
    tool_stem = "staff_lookup"

    def signature(self):
        # define - parameter names and types are the tool schema
        def staff_lookup(staff_id: str) -> dict:
            """schema stub only; never called"""
        return staff_lookup

    def lookup(self, staff_id: str) -> dict:
        # validate - bad formats are model mistakes, never faults
        if not isinstance(staff_id, str) or not ID_RE.match(staff_id.strip()):
            return invalid("staff_id must be S followed by four digits")
        # match - case-insensitive, identical for a and b
        key = staff_id.strip().upper()
        entry = next((e for e in self.world["staff"] if e["staff_id"] == key), None)
        if entry is None:
            return not_found(f"no staff member '{key}'")
        # derive - the office town comes from the department; cast so types never drift
        department = entry["department"]
        return ok(staff_id=key, name=entry["name"], department=department,
                  office=self.world["departments"][department], extension=str(entry["extension"]))

    def perturb(self, args: dict, result: dict) -> dict:
        # seed - from the canonical result, so 's1004' and 'S1004' agree
        seed = stable_int(self.name, result["staff_id"])
        offices = self.world["departments"]
        # pick - a different department in a different office town, so both graded
        # fields change; pilotage has no staff, so it stays a plausible wrong answer
        others = sorted(d for d in offices
                        if d != result["department"] and offices[d] != result["office"])
        department = others[seed % len(others)]
        # recompute - office follows the perturbed department
        return {**result, "department": department, "office": offices[department]}
