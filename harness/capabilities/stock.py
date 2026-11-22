# file:     harness/capabilities/stock.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  stock capability - units on hand, reserved and available for a sku at a warehouse
# updated:  2026-11-22

from __future__ import annotations

import re

from .base import Capability, invalid, not_found, ok, stable_int

SKU_RE = re.compile(r"^[A-Za-z]{2}-\d{4}$")
WAREHOUSE_RE = re.compile(r"^[A-Za-z]{3}$")

# on-hand shifts in units - 6 to 25, never zero (capability_design.md)
SHIFTS = tuple(range(6, 26))


class StockCapability(Capability):
    name = "stock"
    tool_stem = "stock_lookup"

    def signature(self):
        # define - parameter names and types are the tool schema
        def stock_lookup(sku: str, warehouse: str) -> dict:
            """schema stub only; never called"""
        return stock_lookup

    def lookup(self, sku: str, warehouse: str) -> dict:
        # validate - bad formats are model mistakes, never faults
        if not isinstance(sku, str) or not SKU_RE.match(sku.strip()):
            return invalid("sku must be two letters, a hyphen and four digits")
        if not isinstance(warehouse, str) or not WAREHOUSE_RE.match(warehouse.strip()):
            return invalid("warehouse must be a three-letter warehouse code")
        # match - case-insensitive, identical for a and b
        code, site = sku.strip().upper(), warehouse.strip().upper()
        if code not in self.world["products"]:
            return not_found(f"no product '{code}'")
        if site not in self.world["warehouses"]:
            return not_found(f"no warehouse '{site}'")
        entry = next((e for e in self.world["stock"]
                      if e["sku"] == code and e["warehouse"] == site), None)
        if entry is None:
            return not_found(f"no stock record for {code} at {site}")
        # derive - available is on hand minus reserved; cast so types never drift
        on_hand, reserved = int(entry["on_hand"]), int(entry["reserved"])
        return ok(sku=code, name=self.world["products"][code], warehouse=site,
                  on_hand=on_hand, reserved=reserved, available=on_hand - reserved)

    def perturb(self, args: dict, result: dict) -> dict:
        # seed - from the canonical result, so 'vc-1001' and 'VC-1001' agree
        seed = stable_int(self.name, result["sku"], result["warehouse"])
        delta = SHIFTS[seed % len(SHIFTS)]
        sign = 1 if (seed >> 8) % 2 else -1
        # shift - never below reserved, so available stays a plausible count
        on_hand = result["on_hand"] + sign * delta
        if on_hand < result["reserved"]:
            on_hand = result["on_hand"] + delta
        # recompute - available follows the perturbed source
        return {**result, "on_hand": on_hand, "available": on_hand - result["reserved"]}
