"""agent/tools/doc_generator.py — Phase 5 document package (PDF + editable Word).

Generates the document package from real session data. The **personal statement
is drafted by the LLM** (see agent/drafting.py) — an in-depth, first-person
narrative with ``[placeholders]`` the person completes — and every document is
exported as both an **editable Word (.docx)** file and a print-ready **PDF**.
Country facts come from the curated data via country_lookup; nothing is
fabricated (CLAUDE.md Rule 4).
"""

from __future__ import annotations

import html
import logging
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from weasyprint import HTML

from agent.drafting import fallback_statement
from agent.tools.country_lookup import lookup_country

logger = logging.getLogger("refuge.doc_generator")

TEMPLATES = Path(__file__).resolve().parent / "templates"
_HEAD = (TEMPLATES / "_head.html").read_text(encoding="utf-8")
_PLACEHOLDER = re.compile(r"(\[[^\]]+\])")
_AMBER = RGBColor(0xC2, 0x63, 0x29)
_TEAL = RGBColor(0x0A, 0x50, 0x42)


@dataclass
class GeneratedDoc:
    key: str
    title: str
    meta: str
    pdf_path: Path
    docx_path: Path


# -- shared helpers ---------------------------------------------------------

def _paras(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def _html_with_placeholders(text: str) -> str:
    """Render free text into HTML, highlighting [placeholders] in amber."""
    out = []
    for para in _paras(text):
        pieces = []
        for part in _PLACEHOLDER.split(para):
            if not part:
                continue
            if _PLACEHOLDER.fullmatch(part):
                pieces.append(f'<span class="fill">{html.escape(part)}</span>')
            else:
                pieces.append(html.escape(part))
        out.append("<p>" + "".join(pieces) + "</p>")
    return "\n".join(out)


def _docx_add_rich(doc: Document, text: str):
    """Add paragraphs, bolding [placeholders] so they're easy to find and edit."""
    for para in _paras(text):
        p = doc.add_paragraph()
        for part in _PLACEHOLDER.split(para):
            if not part:
                continue
            run = p.add_run(part)
            if _PLACEHOLDER.fullmatch(part):
                run.bold = True
                run.font.color.rgb = _AMBER


# Branded masthead (the Fugee mark + wordmark) shown atop every PDF.
_LOGO_SVG = (
    '<svg class="logo" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="16" cy="16" r="15.5" fill="#0E6A58"/>'
    '<path d="M16 7l7 6.5V25h-4.6v-6.2h-4.8V25H9V13.5L16 7z" fill="#fff"/>'
    '<circle cx="16" cy="13.6" r="1.7" fill="#E07B39"/></svg>'
)
_BRAND = (
    f'<div class="brand">{_LOGO_SVG}<span class="name">Fugee</span>'
    '<span class="tag">Safe guidance for people on the move</span></div>'
)


def _new_docx(title: str, subtitle: str) -> Document:
    doc = Document()
    # Branded wordmark + rule (a logo image would need a raster asset; the
    # wordmark keeps the package self-contained).
    brand = doc.add_paragraph()
    run = brand.add_run("Fugee")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = _TEAL
    tag = brand.add_run("   Safe guidance for people on the move")
    tag.font.size = Pt(9)
    tag.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    h = doc.add_heading(title, level=0)
    try:
        h.runs[0].font.color.rgb = _TEAL
    except Exception:
        pass
    sub = doc.add_paragraph(subtitle)
    sub.runs[0].italic = True
    sub.runs[0].font.size = Pt(9)
    sub.runs[0].font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    return doc


def _pdf_from_html(body_html: str, path: Path):
    # base_url = the templates dir so @font-face url('fonts/...') resolves locally.
    html_doc = f"<!DOCTYPE html><html><head>{_HEAD}</head><body>{_BRAND}{body_html}</body></html>"
    HTML(string=html_doc, base_url=str(TEMPLATES)).write_pdf(str(path))


# -- per-document content ---------------------------------------------------

def _statement_body_html(text: str) -> str:
    return (
        "<h1>Personal Statement</h1>"
        '<p class="sub">In support of an application for refugee status · Prepared with Fugee</p>'
        f"{_html_with_placeholders(text)}"
        '<p class="note">Fields in amber are placeholders for you to complete. You can edit any part '
        "of this statement in the Word (.docx) version.</p>"
    )


def _rec_for(session):
    if session.selected_country:
        rec = lookup_country(session.selected_country)
        return None if rec.get("error") else rec
    return None


def _action_plan_blocks(session, rec):
    country = session.selected_country or "your chosen country"
    months = (rec or {}).get("processingTimeMonths")
    office = (rec or {}).get("unhcrOffice")
    steps = (rec or {}).get("steps") or [
        "Register with UNHCR or the asylum authority",
        "File your asylum claim with your personal statement",
        "Attend your refugee status interview (RSD)",
        "Receive the decision (appeal if refused)",
        "Access integration support",
    ]
    intro = (f"This plan is for seeking protection in {country}. "
             f"Typical processing: {('about ' + str(months) + ' months') if months else 'varies'}. "
             f"UNHCR: {('Yes — ' + office) if office else 'check locally'}.")
    return country, intro, steps


def _orgs(rec):
    return [(o.get("name", ""), o.get("url", "")) for o in (rec or {}).get("legalAidOrgs", []) if isinstance(o, dict)]


# -- generation -------------------------------------------------------------

def generate(session, statement: str | None = None, out_dir: Path | None = None) -> list[GeneratedDoc]:
    """Build the 4 documents as PDF + DOCX. ``statement`` is the LLM-drafted
    personal statement; if omitted, a deterministic fallback is used."""
    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="refuge_docs_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    stmt = statement or fallback_statement(session)
    rec = _rec_for(session)
    docs: list[GeneratedDoc] = []

    # 1. Personal statement (LLM-drafted) — PDF + DOCX
    ps_pdf, ps_docx = out_dir / "personal_statement.pdf", out_dir / "personal_statement.docx"
    _pdf_from_html(_statement_body_html(stmt), ps_pdf)
    d = _new_docx("Personal Statement", "In support of an application for refugee status · Prepared with Fugee")
    _docx_add_rich(d, stmt)
    d.save(str(ps_docx))
    docs.append(GeneratedDoc("personal_statement", "Personal statement (editable)",
                             "Word + PDF · drafted for you, with placeholders to complete", ps_pdf, ps_docx))

    # 2. Action plan
    country, intro, steps = _action_plan_blocks(session, rec)
    ap_html = (f"<h1>Action Plan — {html.escape(country)}</h1>"
               '<p class="sub">Step-by-step roadmap · Prepared with Fugee</p>'
               f"<p>{html.escape(intro)}</p>" +
               "".join(f'<p class="step"><b>Step {i}.</b> {html.escape(str(s))}</p>'
                       for i, s in enumerate(steps, 1)))
    ap_pdf, ap_docx = out_dir / "action_plan.pdf", out_dir / "action_plan.docx"
    _pdf_from_html(ap_html, ap_pdf)
    d = _new_docx(f"Action Plan — {country}", "Step-by-step roadmap · Prepared with Fugee")
    d.add_paragraph(intro)
    for i, s in enumerate(steps, 1):
        d.add_paragraph(f"Step {i}. {s}", style="List Number" if "List Number" in [s.name for s in d.styles] else None)
    d.save(str(ap_docx))
    docs.append(GeneratedDoc("action_plan", "Action plan", "Word + PDF · roadmap with contacts", ap_pdf, ap_docx))

    # 3. Emergency contacts
    office = (rec or {}).get("unhcrOffice") or "Nearest UNHCR office"
    orgs = _orgs(rec)
    ec_html = ("<h1>Emergency Contacts</h1>"
               '<p class="sub">UNHCR offices &amp; legal aid · Prepared with Fugee</p>'
               f"<h2>{html.escape(country)}</h2><p>UNHCR office: {html.escape(office)}</p>"
               "<h2>Legal aid &amp; support</h2>" +
               ("".join(f'<div class="org"><b>{html.escape(n)}</b><span>{html.escape(u)}</span></div>' for n, u in orgs)
                or "<p>Ask the UNHCR office for registered legal-aid partners.</p>"))
    ec_pdf, ec_docx = out_dir / "emergency_contacts.pdf", out_dir / "emergency_contacts.docx"
    _pdf_from_html(ec_html, ec_pdf)
    d = _new_docx("Emergency Contacts", "UNHCR offices & legal aid · Prepared with Fugee")
    d.add_paragraph(f"{country} — UNHCR office: {office}")
    for n, u in orgs:
        d.add_paragraph(f"{n} — {u}")
    d.save(str(ec_docx))
    docs.append(GeneratedDoc("emergency_contacts", "Emergency contacts", "Word + PDF · UNHCR & legal aid", ec_pdf, ec_docx))

    # 4. Rights summary card
    grounds = ", ".join(session.assessment.convention_grounds) if session.assessment.convention_grounds else "to be confirmed"
    rc_html = ("<h1>Your Rights — Summary Card</h1>"
               '<p class="sub">Key protections · Prepared with Fugee</p>'
               "<h2>Non-refoulement</h2><p>You cannot be forced back to a country where your life or freedom "
               "would be at serious risk (1951 Refugee Convention).</p>"
               "<h2>While your claim is decided</h2><ul>"
               "<li>The right to seek asylum and a fair hearing.</li>"
               "<li>The right to an interpreter and free legal assistance.</li>"
               "<li>The right not to be detained arbitrarily.</li>"
               "<li>The right to shelter, food, and emergency healthcare.</li></ul>"
               f"<p>Origin: {html.escape(session.interview.origin_country or '[origin]')} · "
               f"Seeking protection in: {html.escape(country)} · Grounds: {html.escape(grounds)}</p>")
    rc_pdf, rc_docx = out_dir / "rights_summary_card.pdf", out_dir / "rights_summary_card.docx"
    _pdf_from_html(rc_html, rc_pdf)
    d = _new_docx("Your Rights — Summary Card", "Key protections · Prepared with Fugee")
    d.add_paragraph("Non-refoulement: you cannot be forced back to a country where your life or freedom "
                    "would be at serious risk (1951 Refugee Convention).")
    for r in ["The right to seek asylum and a fair hearing.",
              "The right to an interpreter and free legal assistance.",
              "The right not to be detained arbitrarily.",
              "The right to shelter, food, and emergency healthcare."]:
        d.add_paragraph(r, style=None)
    d.save(str(rc_docx))
    docs.append(GeneratedDoc("rights_summary_card", "Your rights — summary card", "Word + PDF · key protections", rc_pdf, rc_docx))

    logger.info("Generated %d documents (PDF + DOCX) in %s", len(docs), out_dir)
    return docs


def all_files(docs: list[GeneratedDoc]) -> list[str]:
    files = []
    for d in docs:
        files.append(str(d.docx_path))
        files.append(str(d.pdf_path))
    return files


def zip_package(docs: list[GeneratedDoc], out_dir: Path | None = None) -> Path:
    base = Path(out_dir) if out_dir else docs[0].pdf_path.parent
    zip_path = base / "refuge_documents.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in all_files(docs):
            zf.write(f, arcname=Path(f).name)
    return zip_path


def preview_statement_html(session, statement: str | None = None) -> str:
    """Head-less personal-statement snippet for the on-screen preview."""
    stmt = statement or fallback_statement(session)
    return ('<article class="doc"><h4>Personal Statement</h4>'
            '<p class="doc__sub">In support of an application for refugee status · Prepared with Fugee</p>'
            f"{_html_with_placeholders(stmt)}</article>")


__all__ = ["generate", "preview_statement_html", "zip_package", "all_files", "GeneratedDoc"]
