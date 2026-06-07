"""scripts/validate_design_tokens.py — T010 / SC-006 token validator.

Pure-Python (no Node/npm linter). Confirms that:

  1. every CSS custom property defined in the app's injected ``:root`` block
     resolves to a real DESIGN.md token with a matching value, and
  2. every ``var(--token)`` referenced anywhere in ``app/app.py`` is defined in
     that ``:root`` block (no undefined / dangling tokens).

Exit code 0 = all tokens resolve; 1 = at least one mismatch or dangling var.

Usage::

    python scripts/validate_design_tokens.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.design_tokens import load_tokens, root_css  # noqa: E402

# Every Python module that injects CSS using var(--token) references.
CSS_SOURCES = [
    REPO_ROOT / "app" / "app.py",
    REPO_ROOT / "app" / "phases" / "intake.py",
    REPO_ROOT / "app" / "phases" / "interview.py",
    REPO_ROOT / "app" / "phases" / "assessment.py",
]

_ROOT_DEF_RE = re.compile(r"--([a-z0-9-]+):\s*([^;]+);")
_VAR_USE_RE = re.compile(r"var\(\s*--([a-z0-9-]+)\s*\)")


def main() -> int:
    design_tokens = load_tokens()
    root_block = root_css()

    # 1. Parse the :root definitions the app actually injects.
    root_defs = {name: value.strip() for name, value in _ROOT_DEF_RE.findall(root_block)}

    errors: list[str] = []

    # Every :root definition must match a DESIGN.md token value exactly.
    for name, value in root_defs.items():
        if name not in design_tokens:
            errors.append(f"  :root defines --{name} but DESIGN.md has no such token")
        elif design_tokens[name] != value:
            errors.append(
                f"  --{name}: app value {value!r} != DESIGN.md value {design_tokens[name]!r}"
            )

    # Every var(--x) used in any CSS-bearing module must be defined in :root.
    used: set[str] = set()
    for src in CSS_SOURCES:
        for name in _VAR_USE_RE.findall(src.read_text(encoding="utf-8")):
            used.add(name)
            if name not in root_defs:
                errors.append(
                    f"  {src.relative_to(REPO_ROOT)} uses var(--{name}) not defined in :root"
                )

    print(f"DESIGN.md tokens:        {len(design_tokens)}")
    print(f":root definitions:       {len(root_defs)}")
    print(f"var(--) refs (all CSS):  {len(used)}")

    if errors:
        print("\nFAIL — token validation errors:")
        print("\n".join(errors))
        return 1

    print("\nPASS — every :root token resolves to DESIGN.md and every var(--) is defined.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
