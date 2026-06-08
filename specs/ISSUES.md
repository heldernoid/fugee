# ISSUES.md — Hard-won gotchas & their fixes

> A log of non-obvious problems hit while building Fugee and how they were
> *actually* fixed (after several wrong guesses). Read this before reimplementing
> the interview UI or the assessment/recommendation logic with another agent — it
> will save you the same multi-round debugging loops.
>
> Format per entry: **Symptom → Wrong guesses → Root cause → Fix → How to verify.**

---

## ISSUE 1 — Gradio `CheckboxGroup` renders empty when revealed (the big one)

**Symptom.** In the multi-step interview, the multi-select questions
("Which of these best describe your situation?" → grounds; "Which documents do
you still have?" → documents) showed only the question bubble and the *Continue*
button — **no checkboxes**. Pressing *Continue* once (with nothing selected) then
made the options appear. Sometimes grounds rendered but documents didn't, and in
non-English runs stale controls leaked (all five controls visible at once with
mismatched languages).

**Wrong guesses (none of these worked — don't repeat them):**
1. "Choices set on reveal lag" → pre-mounted each group with its own fixed
   choices. (No.)
2. "Two CheckboxGroups confuse Gradio" → split into one group per question. (No.)
3. "The two render passes coalesce" → added an `await asyncio.sleep(0.2)` between
   a hidden-with-choices frame and a visible frame. (No.)
4. "The reveal must carry `choices` together with `visible`" → emitted a single
   frame with both. (No.)
5. "The chat re-render competes for the paint" → split the turn into two
   round-trips (`.then()`) so the reveal update carries no chat HTML. (No — still
   failed.)

**Root cause.** Toggling a `gr.CheckboxGroup` (and `gr.Radio`) from
`visible=False` to `visible=True` **does not build its option DOM** — it unhides
an empty shell and paints nothing until the *next* interaction re-touches the
component. The failing operation is the **visibility toggle itself**, not timing
and not chat competition. The reason the "press Continue once" workaround
appeared to work: by then the group was already visible, so the follow-up
`choices` update landed on an *already-visible* component — and **setting choices
on an already-visible group renders correctly**.

**Fix.** Never toggle the visibility of a choice control. Mount the radio and
both checkbox groups with `visible=True` and `choices=[]`, and drive them
**only** by their `choices`:
- The active question sets that control's `choices` (in the person's language);
  all other choice controls get `choices=[]`.
- A CSS rule collapses any choice control that currently has no options:
  ```css
  #iv-choice:not(:has(label)),
  #iv-multi:not(:has(label)),
  #iv-multi-docs:not(:has(label)) { display: none !important; }
  ```
  (Gradio puts the `elem_id` on the component's outer `.block` div; the option
  `<label>`s are descendants, so `:has(label)` is true exactly when it has
  options. `show_label=False` ensures an empty group has no stray label.)
- `gr.Dropdown` (country) and `gr.Textbox` (free text) are NOT affected by this
  bug — they toggle `visible` fine. So `control_updates()` returns *choices* for
  radio/grounds/docs and *visible* for country/text.

Relevant code: `app/phases/interview.py` — `control_updates()`, `_clear_controls()`,
`reveal_controls()`, the control mounts in `build()`, and the `:has` CSS in
`INTERVIEW_CSS`.

**Belt-and-suspenders kept:** each turn is still two round-trips — the click
handler advances the conversation and clears the controls; a chained
`.then(reveal_controls)` sets the active control's choices on its own. With the
always-visible model this isn't strictly required, but it keeps the choices
update isolated from the chat re-render.

**How to verify.** Walk the interview to the documents question (in a non-English
language too). The checkboxes must appear immediately, without pressing Continue.
Only one control is ever visible per step. Smoke test without a browser:
```python
ui = build(visible=False)            # inside a gr.Blocks() context
rev = ui.reveal_fn(session, docs_idx)
assert rev[2]["choices"]             # docs group gets options on an always-visible group
```

---

## ISSUE 2 — Non-signatory countries shown as asylum destinations

**Symptom.** A non-signatory with no UNHCR presence (e.g. **Pakistan**) appeared
as a recommended asylum destination, complete with a "Register with UNHCR" / RSD
roadmap — countries that have no asylum system at all.

**Root cause.** The recommendation collector accepted any country the model named
(or that it looked up) via `lookup_country`, including non-signatories. The
roadmap hard-coded "Register with UNHCR" regardless of whether UNHCR is present.

**Fix.**
- Protection-case recommendations now require `rec["isSignatory"]` to be true;
  non-signatories are dropped (`app/phases/assessment.py`, `_collect`).
- The roadmap's first step adapts: "Register with UNHCR" only when
  `rec["unhcrPresence"]`, otherwise "Register your asylum claim" with the national
  asylum authority (`app/phases/recommendations.py`, `roadmap_html`).
- (Economic/non-protection cases deliberately use *non*-signatory work-visa
  countries instead — see ISSUE 3.)

**How to verify.** `lookup_country("Pakistan")["isSignatory"]` is `False`;
`roadmap_html({...,"unhcrPresence":False})` does not contain "Register with UNHCR".

---

## ISSUE 3 — Economic migrants were given an asylum claim

**Symptom.** Someone who left for purely economic reasons ("no jobs, looking for
opportunities") got "Strong match" asylum cards and a UNHCR/RSD roadmap. Economic
migration has **no** right to asylum under the 1951/1969 Conventions.

**Root cause.** The recommendation/roadmap UI ignored `case_type` entirely — it
always rendered asylum cards and an asylum roadmap.

**Fix.** Honest, case-type-aware output end to end:
- Prompt rule: economic hardship is not a protection ground → classify
  `economic_or_other`.
- For `economic_or_other`, recommendations are the curated
  `work_route_countries()` (Gulf labour markets with employer-sponsored work
  visas, each with its honest `strategic_guidance` caveat) — set
  **deterministically**, never the small model's possibly-Western asylum picks.
- Recommendations render "Work route" cards + a labour-migration roadmap (not
  asylum), and the asylum document step is hidden.

Code: `app/prompts/assessment.md`, `agent/tools/country_lookup.py`
(`work_route_countries`), `app/phases/assessment.py`, `app/phases/recommendations.py`.

---

## ISSUE 4 — Assessment sometimes came out "dry" (one sentence, no recommendations)

**Symptom.** For a strong refugee case the assessment occasionally showed a single
bland sentence and produced no country cards (a bad/cold model roll returned
almost nothing parseable).

**Root cause.** The fallback used when the model's narration was thin was itself a
bare one-liner, and recommendations could end up empty.

**Fix.** Make the system robust to a weak model response:
- Derive `case_type`/grounds/risk from the interview when the model leaves them
  blank (`_derive_case`).
- A structured, multi-paragraph deterministic analysis (`_synth_reasoning`):
  situation → Convention ground → risk & why protection must be sought abroad →
  ranked destinations with real data → next steps.
- Guarantee recommendations via a curated `strong_asylum_destinations()` shortlist
  so the screen is never empty. The model's own richer narration is still
  preferred when present.

---

## ISSUE 5 — Layout: screens different widths, nav drifting between screens

**Symptoms & fixes (CSS, in `app/app.py` + each phase):**
- Each phase card shrink-wrapped to its content (different widths per screen).
  The Gradio wrapper column sized to content, so `width:100%` resolved to the
  content width. Fix: tag each outer wrapper `.screen-wrap { width:100% }` and pin
  `.gradio-container { width:100%; max-width:1180px }` so it never shrink-wraps.
- The top nav drifted sideways between screens. Two causes: (a) the container
  shrink-wrap above; (b) a vertical scrollbar appearing on tall screens changed
  the viewport width and re-centred the page. Fix: the width pin, plus
  `html { scrollbar-gutter: stable; overflow-y: scroll }`.

---

## General lessons for a rebuild

- **Gradio dynamic inputs are the sharp edge.** If you need different input
  controls per step, prefer driving a *mounted-visible* component by its data
  (choices/value) over toggling `visible`; or use `@gr.render` to create the
  control fresh each time. Don't toggle a `CheckboxGroup`/`Radio` visible.
- **The interview is deterministic on purpose.** Questions/controls/translations
  are fixed (`app/interview_script.py`); the LLM is used only where it shows
  intelligence (assessment reasoning, document drafting, review summary). This
  removed a whole class of small-model inconsistency bugs.
- **Be robust to a weak model roll.** Always have a deterministic fallback that is
  itself good (rich text + guaranteed recommendations), because a ≤8B model will
  occasionally return little.
- **Correctness is a safety property here.** Never recommend asylum for an
  economic case or a non-signatory destination. Wrong output is worse than no
  output (see `CLAUDE.md`).
- **Verify, don't self-certify.** The author cannot see the browser from the
  agent sandbox; logic/data were verified with tests and smoke scripts, and the
  human verified the pixels. Keep that division of labour in mind.
