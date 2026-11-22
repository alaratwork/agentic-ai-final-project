# file:     harness/capabilities/__init__.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  registry of built capabilities, looked up by name
# updated:  2026-11-22

from .forecast import ForecastCapability

# register - add each capability class here as it lands (phase 5)
CAPABILITIES = {
    "forecast": ForecastCapability,
}
