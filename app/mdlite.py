"""app/mdlite.py — tiny, dependency-free Markdown → HTML for streamed model text.

Handles what small models actually emit: **bold**, *italic*, `code`, # headings,
- / * bullet lists, 1. numbered lists, and blank-line paragraphs. Everything is
HTML-escaped first, so it is safe to render model output.
"""

from __future__ import annotations

import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")
_CODE = re.compile(r"`([^`]+)`")
_H = re.compile(r"^(#{1,6})\s+(.*)$")
_UL = re.compile(r"^\s*[-*]\s+(.*)$")
_OL = re.compile(r"^\s*\d+[.)]\s+(.*)$")


def inline(text: str) -> str:
    s = html.escape(text)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _ITALIC.sub(r"<em>\1</em>", s)
    s = _CODE.sub(r"<code>\1</code>", s)
    return s


def md_to_html(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        h = _H.match(line)
        if h:
            out.append(f"<h4>{inline(h.group(2))}</h4>")
            i += 1
            continue
        if _UL.match(line):
            items = []
            while i < len(lines) and _UL.match(lines[i]):
                items.append(f"<li>{inline(_UL.match(lines[i]).group(1))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if _OL.match(line):
            items = []
            while i < len(lines) and _OL.match(lines[i]):
                items.append(f"<li>{inline(_OL.match(lines[i]).group(1))}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not (
            _H.match(lines[i]) or _UL.match(lines[i]) or _OL.match(lines[i])
        ):
            para.append(lines[i].rstrip())
            i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


__all__ = ["md_to_html", "inline"]
