"""agent/tools/doc_generator.py — Phase 5 document package generator (T049/T050).

Generates four PDFs from the completed session using WeasyPrint + HTML templates
(agent/tools/templates/). Every pre-filled value comes only from
``session.interview`` / ``session.assessment`` / ``session.selected_country`` —
nothing is invented (CLAUDE.md Critical Rule 4). Pre-filled fields are wrapped in
an amber-highlight ``.fill`` span; missing fields render as a blank line (never a
literal "PLACEHOLDER"/"[NAME]"). Every filled field is logged with its source key.

Output PDFs go to an ephemeral temp directory (ARCHITECTURE.md §Security).
"""

from __future__ import annotations

import html
import logging
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from weasyprint import HTML

from agent.tools.country_lookup import lookup_country

logger = logging.getLogger("refuge.doc_generator")

TEMPLATES = Path(__file__).resolve().parent / "templates"
_HEAD = (TEMPLATES / "_head.html").read_text(encoding="utf-8")


@dataclass
class GeneratedDoc:
    key: str
    title: str
    meta: str
    path: Path


# -- field helpers ----------------------------------------------------------

def _is_empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def fill(value, source_key: str, *, fallback_blank: bool = True) -> str:
    """Amber-highlight a pre-filled value, logging its source. Blank if missing."""
    if _is_empty(value):
        return '<span class="blank">&nbsp;</span>' if fallback_blank else ""
    text = ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)
    logger.info("Filling field from session key: %s", source_key)
    return f'<span class="fill">{html.escape(text)}</span>'


def _render(template_name: str, tokens: dict[str, str]) -> str:
    tpl = (TEMPLATES / template_name).read_text(encoding="utf-8")
    tpl = tpl.replace("%%HEAD%%", _HEAD)
    for key, value in tokens.items():
        tpl = tpl.replace(f"%%{key}%%", value)
    return tpl


# -- per-document HTML builders --------------------------------------------

def _personal_statement_html(session) -> str:
    iv = session.interview
    family_clause = ""
    if not _is_empty(iv.family_situation):
        family_clause = f", traveling with {fill(iv.family_situation, 'interview.family_situation')}"
    history_para = ""
    if not _is_empty(iv.free_text_history):
        history_para = f"<p>{fill(iv.free_text_history, 'interview.free_text_history')}</p>"
    return _render("personal_statement.html", {
        "full_name": fill(None, "interview.full_name"),  # not collected — blank to complete
        "origin_country": fill(iv.origin_country, "interview.origin_country"),
        "current_country": fill(iv.current_country, "interview.current_country"),
        "family_clause": family_clause,
        "persecution": fill(iv.persecution_types, "interview.persecution_types"),
        "history_para": history_para,
    })


def _action_plan_html(session, rec: dict | None) -> str:
    country = session.selected_country or "your chosen country"
    months = (rec or {}).get("processingTimeMonths")
    processing = f"about {months} months" if months else "a variable amount of time"
    office = (rec or {}).get("unhcrOffice")
    unhcr = f"Yes — {office}" if office else ("Yes" if (rec or {}).get("unhcrPresence") else "Check locally")
    steps_src = (rec or {}).get("steps") or [
        "Register with UNHCR or the asylum authority",
        "File your asylum claim with your personal statement",
        "Attend your refugee status interview (RSD)",
        "Receive the decision (appeal if refused)",
        "Access integration support",
    ]
    steps_html = "".join(
        f'<p class="step"><b>Step {i}.</b> {html.escape(str(s))}</p>'
        for i, s in enumerate(steps_src, start=1)
    )
    return _render("action_plan.html", {
        "selected_country": html.escape(str(country)),
        "processing": processing,
        "unhcr_office": html.escape(str(unhcr)),
        "steps": steps_html,
    })


def _emergency_contacts_html(session, rec: dict | None) -> str:
    country = session.selected_country or "your chosen country"
    office = (rec or {}).get("unhcrOffice") or "Nearest UNHCR office"
    orgs = (rec or {}).get("legalAidOrgs") or []
    if orgs:
        orgs_html = "".join(
            f'<div class="org"><b>{html.escape(str(o.get("name", "")))}</b>'
            f'<span>{html.escape(str(o.get("url", "")))}</span></div>'
            for o in orgs if isinstance(o, dict)
        )
    else:
        orgs_html = "<p>Ask the UNHCR office for a list of registered legal-aid partners.</p>"
    return _render("emergency_contacts.html", {
        "selected_country": html.escape(str(country)),
        "unhcr_office": html.escape(str(office)),
        "orgs": orgs_html,
    })


def _rights_card_html(session) -> str:
    grounds = session.assessment.convention_grounds or []
    grounds_txt = ", ".join(grounds) if grounds else "to be confirmed in your interview"
    return _render("rights_summary_card.html", {
        "origin_country": fill(session.interview.origin_country, "interview.origin_country"),
        "selected_country": html.escape(str(session.selected_country or "your chosen country")),
        "grounds": html.escape(grounds_txt),
    })


# -- public API -------------------------------------------------------------

_DOCS = [
    ("personal_statement", "Personal statement (pre-filled)", "PDF · narrative for your claim"),
    ("action_plan", "Action plan", "PDF · step-by-step roadmap with contacts"),
    ("emergency_contacts", "Emergency contacts", "PDF · UNHCR offices & legal aid"),
    ("rights_summary_card", "Your rights — summary card", "PDF · key protections"),
]


def build_html(session) -> dict[str, str]:
    """Return {key: full_html} for all four documents (handy for tests/preview)."""
    rec = None
    if session.selected_country:
        looked = lookup_country(session.selected_country)
        rec = None if looked.get("error") else looked
    return {
        "personal_statement": _personal_statement_html(session),
        "action_plan": _action_plan_html(session, rec),
        "emergency_contacts": _emergency_contacts_html(session, rec),
        "rights_summary_card": _rights_card_html(session),
    }


def preview_statement_html(session) -> str:
    """Inline (head-less) personal-statement snippet for the on-screen preview."""
    iv = session.interview
    family_clause = ""
    if not _is_empty(iv.family_situation):
        family_clause = f", traveling with {fill(iv.family_situation, 'interview.family_situation')}"
    history = ""
    if not _is_empty(iv.free_text_history):
        history = f"<p>{fill(iv.free_text_history, 'interview.free_text_history')}</p>"
    return (
        '<article class="doc"><h4>Personal Statement</h4>'
        '<p class="doc__sub">In support of an application for refugee status · Prepared with Refuge</p>'
        f"<p>My name is {fill(None, 'interview.full_name')}. I am a national of "
        f"{fill(iv.origin_country, 'interview.origin_country')}. I am currently in "
        f"{fill(iv.current_country, 'interview.current_country')}{family_clause}.</p>"
        '<div class="doc__divider"></div>'
        f"<p>I left my home because of {fill(iv.persecution_types, 'interview.persecution_types')}.</p>"
        f"{history}"
        "</article>"
    )


def generate(session, out_dir: Path | None = None) -> list[GeneratedDoc]:
    """Generate the four PDFs. Returns GeneratedDoc records with file paths."""
    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="refuge_docs_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    htmls = build_html(session)

    docs: list[GeneratedDoc] = []
    for key, title, meta in _DOCS:
        path = out_dir / f"{key}.pdf"
        HTML(string=htmls[key]).write_pdf(str(path))
        docs.append(GeneratedDoc(key=key, title=title, meta=meta, path=path))
    logger.info("Generated %d documents in %s", len(docs), out_dir)
    return docs


def zip_package(docs: list[GeneratedDoc], out_dir: Path | None = None) -> Path:
    """Bundle the generated PDFs into a single zip for "Download all"."""
    base = Path(out_dir) if out_dir else docs[0].path.parent
    zip_path = base / "refuge_documents.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in docs:
            zf.write(d.path, arcname=d.path.name)
    return zip_path


__all__ = [
    "generate", "build_html", "preview_statement_html", "zip_package", "GeneratedDoc", "fill",
]
