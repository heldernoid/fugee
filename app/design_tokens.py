"""app/design_tokens.py — single source for DESIGN.md tokens in Python.

DESIGN.md is the canonical design system (CLAUDE.md Design Rule 7). To guarantee
the Gradio app can never drift from it, both the app's injected ``:root`` CSS
block and the T010 token validator are derived from this one parser. No hardcoded
hex values live in the Python UI code (ARCHITECTURE.md §4 theming contract).

The parser reads the YAML frontmatter of DESIGN.md without a YAML dependency —
it only needs the flat ``colors``, ``typography`` (font families), ``rounded``,
and ``spacing`` maps, all of which are simple ``key: "value"`` lines.
"""

from __future__ import annotations

import re
from pathlib import Path

# Repo root = two levels up from this file (app/ -> repo).
REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_MD = REPO_ROOT / "DESIGN.md"

# Sections of the frontmatter we map to CSS custom properties, and the prefix
# each becomes under :root.
_SECTION_PREFIX = {
    "colors": "color",
    "rounded": "radius",
    "spacing": "space",
}

# Within typography we only lift the two font-family declarations to vars.
_FONT_KEYS = {"font-display", "font-ui"}

_SECTION_RE = re.compile(r"^([a-z0-9-]+):\s*$")
_KV_RE = re.compile(r'^\s+([a-z0-9-]+):\s*"(.*?)"')


def load_tokens(design_md: Path | None = None) -> dict[str, str]:
    """Parse DESIGN.md frontmatter into a flat {css-var-name: value} map.

    Keys are the full CSS custom property names without the leading ``--``,
    e.g. ``color-primary``, ``font-display``, ``radius-md``, ``space-lg``.
    """
    path = design_md or DESIGN_MD
    text = path.read_text(encoding="utf-8")

    # Frontmatter is the first block fenced by --- ... ---.
    if text.startswith("---"):
        end = text.find("\n---", 3)
        frontmatter = text[3:end] if end != -1 else text
    else:
        frontmatter = text

    tokens: dict[str, str] = {}
    section: str | None = None

    for line in frontmatter.splitlines():
        sect = _SECTION_RE.match(line)
        if sect:
            section = sect.group(1)
            continue
        if section is None:
            continue

        kv = _KV_RE.match(line)
        if not kv:
            continue
        key, value = kv.group(1), kv.group(2)

        if section in _SECTION_PREFIX:
            tokens[f"{_SECTION_PREFIX[section]}-{key}"] = value
        elif section == "typography" and key in _FONT_KEYS:
            tokens[key] = value

    return tokens


def root_css(design_md: Path | None = None) -> str:
    """Render DESIGN.md tokens as a CSS ``:root`` custom-property block."""
    tokens = load_tokens(design_md)
    lines = [f"  --{name}: {value};" for name, value in tokens.items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


__all__ = ["load_tokens", "root_css", "DESIGN_MD", "REPO_ROOT"]
