# file:     harness/capabilities/__init__.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  registry of built capabilities, looked up by name
# updated:  2026-11-22

from .ferry import FerryCapability
from .forecast import ForecastCapability
from .fx import FxCapability
from .staff import StaffCapability
from .stock import StockCapability

# register - every capability in data/world/ has a class here
CAPABILITIES = {
    "forecast": ForecastCapability,
    "fx": FxCapability,
    "stock": StockCapability,
    "ferry": FerryCapability,
    "staff": StaffCapability,
}
