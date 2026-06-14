"""agent/drafting.py — LLM-drafted asylum documents (the agentic document step).

Uses the agent loop to draft an in-depth, first-person personal statement from
the person's own answers, in their language, inserting clearly-marked
``[placeholders]`` for specifics not collected (name, dates, names of people/
places) so they can complete and edit it. Facts are never invented (AGENTS.md
Rule 4) — the model expands respectfully only on what the person said.
"""

from __future__ import annotations

from agent.events import ErrorEvent, TextDeltaEvent
from agent.loop import create_loop

_SYSTEM = """You are Fugee, helping a person draft a first-person PERSONAL STATEMENT
to support an asylum / refugee claim. Write with dignity, in plain, clear language,
in {language}.

Rules:
- Use ONLY the facts provided. Do not invent events, dates, names, or details.
- Where a specific fact is missing (full name, date of birth, exact dates, names
  of people or places, document numbers), insert a clearly marked placeholder in
  square brackets, e.g. [your full name], [date], [town], so the person can fill it in.
- Expand respectfully on what the person told you about why they left — do not
  exaggerate or add claims they did not make.
- Structure: 4–6 short paragraphs covering, in the first person ("I"):
  1) who I am and where I am from; 2) where I am now; 3) what happened that forced
  me to leave; 4) why I fear returning; 5) the protection I am asking for.
- End with two lines: "Signed: [your full name]" and "Date: [date]".
- Output ONLY the statement text. No headings, no commentary, no markdown."""


def _facts(session) -> str:
    iv = session.interview
    rows = [
        ("Country of origin", iv.origin_country),
        ("Current country", iv.current_country),
        ("What happened (their words)", iv.free_text_history
         or (", ".join(iv.persecution_types) if iv.persecution_types else None)),
        ("In immediate danger", None if iv.immediate_danger is None else ("yes" if iv.immediate_danger else "no")),
        ("Time since leaving", iv.displacement_duration),
        ("Travelling with", iv.family_situation),
        ("Languages", ", ".join(iv.languages_spoken) if iv.languages_spoken else None),
        ("Seeking protection in", session.selected_country),
    ]
    return "\n".join(f"- {k}: {v}" for k, v in rows if v)


async def draft_personal_statement(session, loop=None) -> str:
    """Draft the statement via the LLM. Returns plain text with [placeholders]."""
    loop = loop or create_loop()
    language = getattr(session, "language", None) or "English"
    system_prompt = _SYSTEM.format(language=language)
    prompt = (
        "Draft my personal statement now using these facts:\n\n" + _facts(session)
        + "\n\nWrite it in " + language + "."
    )
    acc = ""
    async for ev in loop.run(prompt, session=None, system_prompt=system_prompt, thinking_level="off"):
        if isinstance(ev, TextDeltaEvent):
            acc += ev.delta
        elif isinstance(ev, ErrorEvent):
            acc += ""  # fall back to template below if the model failed
    return acc.strip()


def fallback_statement(session) -> str:
    """Deterministic statement if the model is unavailable (no fabrication)."""
    iv = session.interview
    origin = iv.origin_country or "[country of origin]"
    current = iv.current_country or "[current country]"
    reason = iv.free_text_history or "[describe what happened that made you leave]"
    return (
        f"My name is [your full name]. I am a national of {origin}, born in [town] on [date of birth].\n\n"
        f"I am currently in {current}.\n\n"
        f"I had to leave {origin} because: {reason}\n\n"
        "I fear that if I am returned I will be at serious risk of harm for the reasons described above.\n\n"
        "I am asking for protection and the right not to be returned to a place where my life or freedom "
        "would be threatened.\n\n"
        "Signed: [your full name]\nDate: [date]"
    )


__all__ = ["draft_personal_statement", "fallback_statement"]
