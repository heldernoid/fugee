"""app/design_tokens.py — single source for DESIGN.md tokens in Python.

DESIGN.md is the canonical design system (AGENTS.md) and
``mockup.html`` is the visual reference. To guarantee the Gradio app matches
both, this module parses DESIGN.md's YAML frontmatter and emits CSS custom
properties using the **same variable names as mockup.html** (``--primary``,
``--bg``, ``--text``, ``--r-md``, ``--s-md`` …). That way the phase CSS can be
lifted from the mockup verbatim and stay token-faithful.

A few tokens that mockup.html uses live in DESIGN.md prose (§4 Layout, §5
Elevation) rather than the frontmatter — the shadows and the max reading width.
Those are declared here as ``PROSE_TOKENS`` with their DESIGN.md source noted.

No hardcoded hex values live in the Python UI code (ARCHITECTURE.md §4).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_MD = REPO_ROOT / "DESIGN.md"

# DESIGN.md frontmatter sections we lift, and how each key becomes a CSS var.
# Most keys map to "<prefix><key>"; a few colours are renamed to match the
# mockup's shorter names (background -> bg, text-primary -> text).
_COLOR_RENAME = {"background": "bg", "text-primary": "text"}
_PREFIX = {"rounded": "r-", "spacing": "s-"}

# Typography keys lifted as font-family vars.
_FONT_KEYS = {"font-display", "font-ui"}

# Tokens defined in DESIGN.md prose (not frontmatter) but used by mockup.html.
#   shadows  -> DESIGN.md §5 Elevation & Depth
#   maxw     -> DESIGN.md §4 Layout (max content width 780px)
PROSE_TOKENS: dict[str, str] = {
    "shadow-sm": "0 1px 2px rgba(13,46,38,.06), 0 1px 1px rgba(13,46,38,.04)",
    "shadow-md": "0 6px 20px rgba(13,46,38,.08)",
    "shadow-lg": "0 18px 48px rgba(13,46,38,.12)",
    "maxw": "780px",
}

_SECTION_RE = re.compile(r"^([a-z0-9-]+):\s*$")
_KV_RE = re.compile(r'^\s+([a-z0-9-]+):\s*"(.*?)"')


def load_tokens(design_md: Path | None = None) -> dict[str, str]:
    """Parse DESIGN.md into a flat {css-var-name: value} map (mockup naming).

    Keys are CSS custom-property names without the leading ``--`` — e.g.
    ``primary``, ``bg``, ``text``, ``r-md``, ``s-lg``, ``font-display`` — plus
    the prose-sourced ``shadow-*`` and ``maxw`` tokens.
    """
    path = design_md or DESIGN_MD
    text = path.read_text(encoding="utf-8")

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

        if section == "colors":
            tokens[_COLOR_RENAME.get(key, key)] = value
        elif section in _PREFIX:
            tokens[f"{_PREFIX[section]}{key}"] = value
        elif section == "typography" and key in _FONT_KEYS:
            tokens[key] = value

    tokens.update(PROSE_TOKENS)
    return tokens


def root_css(design_md: Path | None = None) -> str:
    """Render DESIGN.md tokens as a CSS ``:root`` custom-property block."""
    tokens = load_tokens(design_md)
    lines = [f"  --{name}: {value};" for name, value in tokens.items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


__all__ = ["load_tokens", "root_css", "PROSE_TOKENS", "DESIGN_MD", "REPO_ROOT"]
