# file:     scripts/check_descriptions.py
# project:  judging a tool by its cover (group 9, tokens)
# course:   agentic ai
# author:   archit gupta
# purpose:  print all rich and poor descriptions and fail if any breaks the equivalence rules
# updated:  2026-11-23

# rules (fp2 4.5, phase 6 plan): every fact string in both styles, no banned
# quality/status/example words, poor at most two lines, rich longer than poor.
# this is the automated half of the equivalence check; a teammate still reads them.

from __future__ import annotations

import sys
from pathlib import Path

# path - make `harness` importable when run as `python scripts/check_descriptions.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from harness.capabilities import CAPABILITIES  # noqa: E402
from harness.descriptions import STYLES, check, render  # noqa: E402


def main() -> int:
    problems = []
    for name in sorted(CAPABILITIES):
        for style in STYLES:
            text = render(name, style)
            # show - each description as the model will see it, with its size
            print(f"=== {name} / {style} ({len(text.split())} words, {len(text.splitlines())} lines)")
            print(text, end="\n\n")
        problems += check(name)
    for problem in problems:
        print(f"FAIL {problem}")
    count = len(CAPABILITIES) * len(STYLES)
    print(f"{'FAILED' if problems else 'PASSED'}: {count} descriptions, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
