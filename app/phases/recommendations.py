"""app/phases/recommendations.py — Phase 4 country cards + roadmap (T044-T046).

Matches mockup.html #phase-4: 2–3 country cards (flag, Fraunces name, match
badge, a real facts block, an expandable "what to prepare", and a select button),
plus a vertical numbered roadmap for the chosen country that updates when the
person switches cards.

All card facts come from the real ``country_lookup`` records carried on
``session.assessment.recommended_countries`` — never hardcoded or fabricated
(SC-033). Selecting a card sets ``session.selected_country``.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

import gradio as gr

from app.state.session import SessionState

MAX_CARDS = 3

RECO_CSS = """
#reco-screen { background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg); box-shadow: var(--shadow-md); overflow: hidden;
  max-width: 1180px; margin: 0 auto; padding: clamp(18px,4vw,30px); }
.reco__intro { max-width:60ch; color:var(--text-secondary); font-size:15px; margin:0 0 22px; }
#reco-cards { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
@media(max-width:820px){ #reco-cards { grid-template-columns:1fr; } }
.ccard-slot { border:1.5px solid var(--line); border-radius:var(--r-lg); background:var(--surface-2);
  padding:20px; display:flex; flex-direction:column; gap:14px; }
.ccard-slot.is-selected { border-color:var(--primary); box-shadow:0 0 0 3px var(--primary-tint), var(--shadow-md); background:var(--surface); }
.ccard__top { display:flex; align-items:center; gap:11px; }
.ccard__flag { font-size:30px; line-height:1; }
.ccard__name { font-family:var(--font-display); font-weight:600; font-size:21px; color:var(--text); }
.badge { font-size:11.5px; font-weight:700; letter-spacing:.03em; padding:4px 10px; border-radius:var(--r-full); text-transform:uppercase; }
.badge--strong { background:var(--success-tint); color:#1d6b41; }
.badge--moderate { background:var(--warning-tint); color:#8a6414; }
.badge--work { background:var(--accent-tint); color:#8a4a1a; }
.ccard__caveat { font-size:12.5px; line-height:1.5; color:#8a5a2a; background:var(--accent-tint);
  border-radius:var(--r-sm); padding:9px 11px; display:flex; gap:8px; }
.ccard__caveat::before { content:"⚠"; flex:0 0 auto; }
.ccard__facts { display:flex; flex-direction:column; gap:9px; border-top:1px solid var(--line); border-bottom:1px solid var(--line); padding:14px 0; }
.ccard__facts .f { display:flex; justify-content:space-between; gap:10px; font-size:13.5px; }
.ccard__facts .f span { color:var(--text-muted); }
.ccard__facts .f b { color:var(--text); font-weight:600; text-align:right; }
details.prep summary { list-style:none; cursor:pointer; font-size:13.5px; font-weight:600; color:var(--primary-deep); display:flex; align-items:center; gap:7px; padding:2px 0; }
details.prep summary::-webkit-details-marker { display:none; }
details.prep ul { margin:11px 0 0; padding:0; list-style:none; display:flex; flex-direction:column; gap:8px; }
details.prep li { font-size:13.5px; color:var(--text-secondary); display:flex; gap:9px; line-height:1.45; }
details.prep li::before { content:""; flex:0 0 auto; width:6px; height:6px; border-radius:50%; background:var(--accent); margin-top:7px; }

.ccard-slot .btn-card-select, .ccard-slot .btn-card-select button { width:100% !important; border-radius:var(--r-md) !important; font-weight:600 !important;
  background:var(--surface) !important; color:var(--primary-deep) !important; border:1px solid var(--line-strong) !important; box-shadow:none !important; }
.ccard-slot .btn-card-select:hover, .ccard-slot .btn-card-select button:hover { border-color:var(--primary) !important; background:var(--primary-tint) !important; }
.ccard-slot.is-selected .btn-card-select, .ccard-slot.is-selected .btn-card-select button { background:var(--primary) !important; color:var(--on-primary) !important;
  border-color:var(--primary) !important; box-shadow:0 2px 0 var(--primary-deep) !important; }

#reco-roadmap { margin-top:30px; background:var(--surface-2); border:1px solid var(--line); border-radius:var(--r-lg); padding:clamp(18px,4vw,26px); }
.roadmap__head { display:flex; align-items:center; gap:10px; margin-bottom:20px; flex-wrap:wrap; }
.roadmap__head h3 { font-size:18px; font-family:var(--font-display); font-weight:600; margin:0; }
.roadmap__head .for { font-size:13px; color:var(--text-muted); }
.roadmap__head .for b { color:var(--primary-deep); }
.steps { display:flex; flex-direction:column; }
.step { display:grid; grid-template-columns:42px 1fr; gap:16px; position:relative; padding-bottom:22px; }
.step:last-child { padding-bottom:0; }
.step__num { position:relative; z-index:1; width:42px; height:42px; border-radius:var(--r-full); background:var(--primary); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:16px; box-shadow:var(--shadow-sm); }
.step:not(:last-child)::before { content:""; position:absolute; left:20px; top:42px; bottom:0; width:2px; background:var(--primary-tint-2); }
.step__body h4 { font-family:var(--font-ui); font-size:15.5px; font-weight:700; margin:0 0 4px; }
.step__body p { font-size:14px; color:var(--text-secondary); margin:0 0 7px; }
.step__meta { display:flex; gap:8px; flex-wrap:wrap; }
.tag-s { font-size:12px; font-weight:500; color:var(--text-secondary); background:var(--surface); border:1px solid var(--line); padding:3px 10px; border-radius:var(--r-full); display:inline-flex; align-items:center; gap:6px; }
#reco-proceed-row { margin-top:24px; justify-content:center; }
#reco-proceed, #reco-proceed button { background:var(--accent) !important; color:var(--on-accent) !important;
  box-shadow:0 2px 0 var(--accent-deep) !important; border:0 !important; font-weight:600 !important;
  border-radius:var(--r-md) !important; padding:14px 26px !important; }
#reco-proceed:hover, #reco-proceed button:hover { background:var(--accent-deep) !important; }
"""


# --------------------------------------------------------------------------
# Pure rendering / derivation (unit-friendly)
# --------------------------------------------------------------------------

def match_strength(rec: dict) -> str:
    """Derive a match badge from real fields (signatory + UNHCR + tier 1)."""
    if rec.get("isSignatory") and rec.get("unhcrPresence") and rec.get("tier") == 1:
        return "strong"
    return "moderate"


def _processing_label(rec: dict) -> str:
    months = rec.get("processingTimeMonths")
    return f"~{months} months" if months else "Not published"


def _unhcr_label(rec: dict) -> str:
    if rec.get("unhcrPresence"):
        office = rec.get("unhcrOffice")
        return f"Yes — {office}" if office else "Yes"
    return "No"


def _acceptance_label(rec: dict) -> str:
    rate = rec.get("acceptanceRate")
    if rate in (None, "", "PENDING"):
        return "Not published"
    try:
        pct = float(rate)
        pct = pct * 100 if pct <= 1 else pct  # stored as 0-1 fraction
        return f"{round(pct)}%"
    except (TypeError, ValueError):
        return str(rate)


def _language_label(rec: dict) -> str:
    langs = rec.get("languages") or ([rec["primaryLanguage"]] if rec.get("primaryLanguage") else [])
    return ", ".join(langs[:2]) if langs else "—"


def _work_visa_label(rec: dict) -> str:
    wv = rec.get("workVisa") or {}
    if wv.get("exists"):
        req = wv.get("requirement")
        return f"Yes — {req}" if req else "Yes"
    return "Limited"


def card_body_html(rec: dict, economic: bool = False) -> str:
    flag = rec.get("flag", "")
    name = html.escape(rec.get("country", "Unknown"))
    if economic:
        # Work-migration framing — NOT an asylum claim. No recognition rate / RSD.
        badge_cls, badge_txt = "badge--work", "Work route"
        facts = [
            ("Work visa", _work_visa_label(rec)),
            ("Job market", str(rec.get("economicOpportunity") or "—")),
            ("Primary language", _language_label(rec)),
            ("Region", str(rec.get("region") or "—")),
        ]
        facts_html = "".join(
            f'<div class="f"><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>'
            for k, v in facts
        )
        caveat = rec.get("strategicGuidance")
        caveat_html = f'<div class="ccard__caveat">{html.escape(str(caveat))}</div>' if caveat else ""
        prep = [
            "A confirmed job offer from a licensed employer who will sponsor your visa",
            "A valid passport — keep it in your own hands at all times",
            "A written contract you understand before you travel; never pay illegal recruitment fees",
        ]
        prep_items = "".join(f"<li>{html.escape(p)}</li>" for p in prep)
        return (
            '<div class="ccard__top">'
            f'<span class="ccard__flag">{flag}</span>'
            f'<div><div class="ccard__name">{name}</div>'
            f'<span class="badge {badge_cls}">{badge_txt}</span></div></div>'
            f'<div class="ccard__facts">{facts_html}</div>'
            f"{caveat_html}"
            '<details class="prep"><summary>▸ What you need to prepare</summary>'
            f"<ul>{prep_items}</ul></details>"
        )
    strength = match_strength(rec)
    badge_cls = "badge--strong" if strength == "strong" else "badge--moderate"
    badge_txt = "Strong match" if strength == "strong" else "Moderate match"
    facts = [
        ("Processing time", _processing_label(rec)),
        ("UNHCR office", _unhcr_label(rec)),
        ("Recognition rate (recent)", _acceptance_label(rec)),
        ("Primary language", _language_label(rec)),
    ]
    facts_html = "".join(
        f'<div class="f"><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>'
        for k, v in facts
    )
    docs = rec.get("requiredDocuments") or []
    prep_items = "".join(f"<li>{html.escape(str(d))}</li>" for d in docs) or \
        "<li>Fugee will help you gather what you need.</li>"
    return (
        '<div class="ccard__top">'
        f'<span class="ccard__flag">{flag}</span>'
        f'<div><div class="ccard__name">{name}</div>'
        f'<span class="badge {badge_cls}">{badge_txt}</span></div></div>'
        f'<div class="ccard__facts">{facts_html}</div>'
        '<details class="prep"><summary>▸ What you need to prepare</summary>'
        f"<ul>{prep_items}</ul></details>"
    )


def _contact(rec: dict) -> str:
    orgs = rec.get("legalAidOrgs") or []
    if orgs and isinstance(orgs[0], dict):
        return orgs[0].get("name", "Local legal aid")
    office = rec.get("unhcrOffice")
    return f"UNHCR {office}" if office else "UNHCR office"


def _work_roadmap_steps(rec: dict) -> list[tuple]:
    """Honest labour-migration steps (employer-sponsored work visa), not asylum."""
    return [
        ("Find a job offer and a sponsor",
         "A licensed employer must offer you a job and sponsor your work visa. "
         "Use official job portals and licensed recruitment agencies only — never "
         "informal 'agents' or smugglers.",
         "Licensed employer / recruiter", "Varies"),
        ("Employer applies for your work permit",
         "Your sponsor applies to the labour ministry for your work permit and "
         "entry visa. You should not be asked to pay for this yourself.",
         "Sponsor + labour ministry", "Weeks to months"),
        ("Medical, contract and visa",
         "Complete the required medical check and read your contract carefully "
         "before signing. Keep your own passport — do not hand it over.",
         "Embassy / visa centre", "Before travel"),
        ("Arrival and residence permit",
         "On arrival your employer arranges your residence permit (e.g. Iqama/ID). "
         "Confirm your job, pay and housing match your signed contract.",
         "On arrival", "First weeks"),
        ("Know your rights",
         "Sponsorship (kafala) often ties your visa to your employer. Keep copies "
         "of your documents and contact your embassy or a labour helpline if you "
         "are mistreated or unpaid.",
         "Your embassy · labour helpline", "Ongoing"),
    ]


def roadmap_html(rec: dict | None, economic: bool = False) -> str:
    if not rec:
        return '<div id="reco-roadmap" style="display:none"></div>'
    name = html.escape(rec.get("country", ""))
    flag = rec.get("flag", "")
    if economic:
        steps = _work_roadmap_steps(rec)
        head_title = "Your work-route roadmap"
    else:
        office = rec.get("unhcrOffice")
        unhcr_contact = f"UNHCR {office}" if office else "UNHCR office"
        legal = _contact(rec)
        months = rec.get("processingTimeMonths")
        total_time = f"~{months} months total" if months else "varies"
        head_title = "Your roadmap"
        steps = [
            ("Register with UNHCR",
             "Get a registration appointment and an asylum-seeker certificate, which "
             "protects you from being returned.",
             unhcr_contact, "1–4 weeks for appointment"),
            ("File your asylum claim",
             "Submit your personal statement and supporting evidence. Fugee has "
             "already drafted these for you.",
             "Asylum authority / RSD unit", "Same week as registration"),
            ("Refugee status interview (RSD)",
             "A protection officer hears your account. Free legal aid can prepare and "
             "accompany you.",
             legal, "months after filing"),
            ("Decision",
             "If recognised, you receive refugee status. If not, you have the right "
             "to appeal.",
             "Written decision · appeal possible", total_time),
            ("Integration support",
             "Access schooling for your children, healthcare, and the right to work "
             "or a resettlement referral.",
             "UNHCR partners · community orgs", "Ongoing"),
        ]
    rows = []
    for i, (title, desc, contact, time) in enumerate(steps, start=1):
        rows.append(
            '<div class="step">'
            f'<div class="step__num">{i}</div>'
            f'<div class="step__body"><h4>{html.escape(title)}</h4>'
            f"<p>{html.escape(desc)}</p>"
            '<div class="step__meta">'
            f'<span class="tag-s">📍 {html.escape(contact)}</span>'
            f'<span class="tag-s">⏱ {html.escape(time)}</span>'
            "</div></div></div>"
        )
    return (
        f'<div id="reco-roadmap"><div class="roadmap__head"><h3>{html.escape(head_title)}</h3>'
        f'<span class="for">for <b>{flag} {name}</b> · updates if you choose another country</span>'
        f'</div><div class="steps">{"".join(rows)}</div></div>'
    )


def _recs(session: SessionState) -> list[dict]:
    return (session.assessment.recommended_countries or [])[:MAX_CARDS]


def is_economic_case(session: SessionState) -> bool:
    """Economic / non-protection case — asylum cards & RSD roadmap don't apply."""
    return getattr(session.assessment, "case_type", None) == "economic_or_other"


_PROTECTION_INTRO = (
    '<p class="reco__intro">Based on your situation, these are the safest and most '
    "achievable options near you. Each is matched to your profile — not a generic "
    "ranking.</p>"
)
_ECONOMIC_INTRO = (
    '<p class="reco__intro">From what you shared, your situation looks mainly '
    "<b>economic</b> — the search for work and a better income. That is real and "
    "hard, but it is important to be honest: <b>asylum is not the right route for "
    "economic migration</b>, and a refused asylum claim can leave you stuck, unable "
    "to work, and at risk of removal. Instead, here are real <b>work-migration</b> "
    "destinations with active routes for foreign workers — read each one's guidance "
    "carefully, because they come with conditions.</p>"
)


def intro_html(session: SessionState) -> str:
    return _ECONOMIC_INTRO if is_economic_case(session) else _PROTECTION_INTRO


def select_country(session: SessionState, index: int) -> SessionState:
    """Set ``session.selected_country`` to the i-th recommendation (T045)."""
    recs = _recs(session)
    if session is not None and 0 <= index < len(recs):
        session.selected_country = recs[index].get("country")
    return session


# --------------------------------------------------------------------------
# UI assembly
# --------------------------------------------------------------------------

@dataclass
class RecommendationsUI:
    column: gr.Column
    render_outputs: list  # [slot,card,btn]*MAX_CARDS + [roadmap]
    populate: callable     # (session) -> list of updates for render_outputs
    session: gr.State
    proceed: gr.Button     # "Prepare my documents" -> Phase 5


def build(visible: bool = False, session_st: gr.State | None = None) -> RecommendationsUI:
    session_st = session_st or gr.State(None)
    slots, cards, btns = [], [], []

    with gr.Column(visible=visible, elem_classes=["screen-wrap"]) as column:
        with gr.Column(elem_id="reco-screen"):
            intro = gr.HTML(_PROTECTION_INTRO)
            with gr.Row(elem_id="reco-cards"):
                for i in range(MAX_CARDS):
                    with gr.Column(elem_classes=["ccard-slot"], visible=False) as slot:
                        card = gr.HTML("")
                        btn = gr.Button("Select this country", elem_classes=["btn-card-select"])
                    slots.append(slot)
                    cards.append(card)
                    btns.append(btn)
            roadmap = gr.HTML(roadmap_html(None))
            with gr.Row(elem_id="reco-proceed-row"):
                proceed = gr.Button("Prepare my documents →", elem_id="reco-proceed")

    render_outputs = [intro]
    for i in range(MAX_CARDS):
        render_outputs += [slots[i], cards[i], btns[i]]
    render_outputs += [roadmap, proceed]

    def _updates(session: SessionState) -> list:
        recs = _recs(session)
        economic = is_economic_case(session)
        selected = session.selected_country
        out = [gr.update(value=intro_html(session))]
        for i in range(MAX_CARDS):
            if i < len(recs):
                rec = recs[i]
                is_sel = selected == rec.get("country")
                classes = ["ccard-slot", "is-selected"] if is_sel else ["ccard-slot"]
                out.append(gr.update(visible=True, elem_classes=classes))
                out.append(gr.update(value=card_body_html(rec, economic=economic)))
                out.append(gr.update(visible=True, value="✓ Selected" if is_sel else "Select this country"))
            else:
                out.append(gr.update(visible=False))
                out.append(gr.update(value=""))
                out.append(gr.update(visible=False))
        sel_rec = next((r for r in recs if r.get("country") == selected), None)
        out.append(gr.update(value=roadmap_html(sel_rec, economic=economic)))
        # An economic case is not an asylum claim, so don't offer to generate an
        # asylum document package. The work-route guidance is the destination.
        out.append(gr.update(visible=not economic))
        return out

    def populate(session: SessionState) -> list:
        # Auto-select the top (best) country so a roadmap shows immediately.
        recs = _recs(session)
        if recs and not session.selected_country:
            session.selected_country = recs[0].get("country")
        return _updates(session)

    def select(i: int, session: SessionState):
        select_country(session, i)
        return [*_updates(session), session]

    for i in range(MAX_CARDS):
        btns[i].click(
            lambda session, idx=i: select(idx, session),
            inputs=[session_st],
            outputs=[*render_outputs, session_st],
        )

    return RecommendationsUI(
        column=column, render_outputs=render_outputs, populate=populate, session=session_st,
        proceed=proceed,
    )


__all__ = [
    "build",
    "RecommendationsUI",
    "RECO_CSS",
    "MAX_CARDS",
    "match_strength",
    "card_body_html",
    "roadmap_html",
    "select_country",
]
