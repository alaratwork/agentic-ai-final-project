# file:     harness/capabilities/fx.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  fx capability - convert an amount between verrin coast currencies on a date
# updated:  2026-11-22

from __future__ import annotations

import re

from .base import Capability, invalid, normalize, not_found, ok, stable_int

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CODE_RE = re.compile(r"^[A-Za-z]{3}$")

# rate shifts in thousandths - 4% to 9%, never zero (capability_design.md)
SCALES = (40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90)
WIDEN = 0.01  # step used when a shift is too small to change the rounded answer


class FxCapability(Capability):
    name = "fx"
    tool_stem = "fx_convert"

    def signature(self):
        # define - parameter names and types are the tool schema
        def fx_convert(amount: float, base: str, quote: str, date: str) -> dict:
            """schema stub only; never called"""
        return fx_convert

    def lookup(self, amount: float, base: str, quote: str, date: str) -> dict:
        # validate - bad formats are model mistakes, never faults
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
            return invalid("amount must be a positive number")
        for label, code in (("base", base), ("quote", quote)):
            if not isinstance(code, str) or not CODE_RE.match(code.strip()):
                return invalid(f"{label} must be a three-letter currency code")
        if not isinstance(date, str) or not DATE_RE.match(date.strip()):
            return invalid("date must be YYYY-MM-DD, e.g. '2026-12-01'")
        # match - codes are case-insensitive, identical for a and b
        b, q, day = base.strip().upper(), quote.strip().upper(), date.strip()
        if b == q:
            return invalid("base and quote must be different currencies")
        for code in (b, q):
            if code not in self.world["currencies"]:
                return not_found(f"no currency '{code}'")
        values = next((d["values"] for d in self.world["daily_values"] if d["date"] == day), None)
        if values is None:
            return not_found(f"no rates on {day}")
        # derive - rate is quote units per one base unit; cast so types never drift
        rate = round(values[b] / values[q], 4)
        amount = float(amount)
        return ok(base=b, quote=q, date=day, amount=amount, rate=float(rate),
                  converted=float(round(amount * rate, 2)))

    def perturb(self, args: dict, result: dict) -> dict:
        # seed - from the canonical result, so 'kld' and 'KLD' agree
        seed = stable_int(self.name, result["base"], result["quote"], result["date"], result["amount"])
        scale = SCALES[seed % len(SCALES)] / 1000
        sign = 1 if (seed >> 8) % 2 else -1
        # shift - scale the rate; widen until the rounded answer really changes
        while True:
            rate = round(result["rate"] * (1 + sign * scale), 4)
            converted = round(result["amount"] * rate, 2)
            if normalize(converted) != normalize(result["converted"]) or scale >= 0.5:
                break
            scale += WIDEN
        # recompute - converted follows the perturbed rate
        return {**result, "rate": float(rate), "converted": float(converted)}
