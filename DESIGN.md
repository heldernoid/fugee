---
name: Fugee
description: A calm, trustworthy guide that helps displaced people understand their legal options, find safe destination countries, and prepare their documentation — the digital equivalent of a knowledgeable, compassionate case worker.

colors:
  primary: "#0E6A58"        # deep trustworthy teal-green
  primary-deep: "#0A5042"   # darker teal for shadows, pressed states, text on tint
  primary-tint: "#E5EFEA"   # pale teal wash for agent bubbles, surfaces, hovers
  primary-tint-2: "#D2E3DC" # slightly stronger teal wash for borders/tracks
  secondary: "#2E7D6C"      # lighter supporting teal (gradients, accents)
  accent: "#E07B39"         # warm amber — calls to action, highlights, the user
  accent-deep: "#C26329"    # darker amber for hover/pressed/button shadow
  accent-tint: "#FBEDE1"    # pale amber wash for user bubbles, highlight fills
  background: "#F7F5F0"     # warm off-white page background
  surface: "#FFFFFF"        # cards, screens, primary surfaces
  surface-2: "#FCFBF7"      # subtly warmer surface for nested panels/footers
  text-primary: "#1A1A1A"   # near-black body and headings
  text-secondary: "#51596A" # muted slate for supporting copy (AA on background)
  text-muted: "#6B7280"     # gray for labels, captions, metadata
  line: "#E7E2D8"           # default hairline border (warm)
  line-strong: "#D8D2C5"    # stronger border for inputs, dividers
  success: "#2C8A59"        # checks, strong matches, positive findings
  success-tint: "#E4F1EA"   # success badge / fill background
  warning: "#B5841C"        # moderate match, caution
  warning-tint: "#F6ECD6"   # warning badge / fill background
  danger: "#BE3F2C"         # errors, destructive only — used sparingly
  on-primary: "#FFFFFF"     # text/icons on primary teal
  on-accent: "#FFFFFF"      # text/icons on accent amber

typography:
  font-display: "Fraunces, Georgia, 'Times New Roman', serif"
  font-ui: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
  h1:      { font: display, size: "clamp(38px, 6vw, 58px)", weight: 600, line: 1.15, tracking: "-0.02em" }
  h2:      { font: display, size: "28px", weight: 600, line: 1.18, tracking: "-0.01em" }
  h3:      { font: display, size: "20px", weight: 600, line: 1.2,  tracking: "-0.005em" }
  body-lg: { font: ui, size: "18px", weight: 450, line: 1.6 }
  body-md: { font: ui, size: "15px", weight: 400, line: 1.6 }
  body-sm: { font: ui, size: "13.5px", weight: 400, line: 1.55 }
  label:   { font: ui, size: "12px", weight: 600, line: 1.3, tracking: "0.06em", transform: uppercase }
  caption: { font: ui, size: "12px", weight: 400, line: 1.45, color: text-muted }

rounded:
  sm: "4px"     # inputs nested elements, small chips
  md: "8px"     # buttons, inputs, cards' inner blocks
  lg: "16px"    # screen frames, country cards, panels
  full: "9999px" # pills, badges, avatars, progress dots

spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
  xxl: "64px"

components:
  button-primary:   { bg: accent, text: on-accent, radius: md, pad: "13px 22px", weight: 600, shadow: "0 2px 0 accent-deep", hover-bg: accent-deep }
  button-secondary: { bg: surface, text: primary-deep, border: "1px line-strong", radius: md, pad: "13px 22px", weight: 600, hover-bg: primary-tint, hover-border: primary }
  button-ghost:     { bg: transparent, text: primary-deep, radius: md, pad: "10px 14px", weight: 600, hover-bg: primary-tint }
  input-field:      { bg: surface, border: "1.5px primary-tint-2", radius: md, pad: "13px 16px", focus-border: primary, focus-ring: "0 0 0 4px primary-tint" }
  phase-pill:       { dot: "22px full", states: ["done: primary fill, white check", "active: accent fill + 4px accent-tint halo", "upcoming: surface, line-strong border, muted number"] }
  message-agent:    { bg: primary-tint, text: "#15302a", radius: "14px (5px bottom-left)", avatar: "primary circle, white mark" }
  message-user:     { bg: accent-tint, text: "#5c3415", radius: "14px (5px bottom-right)", align: right, avatar: "accent circle" }
  country-card:     { bg: surface-2, border: "1.5px line", radius: lg, pad: "20px", selected: "primary border + 3px primary-tint ring + surface bg" }
  language-pill:    { bg: surface, border: "1px line-strong", radius: full, pad: "9px 16px", selected: "primary fill, on-primary text" }
  document-item:    { bg: surface, border: "1px line", radius: md, pad: "13px 14px", icon: "38px primary-tint square", action: "38px download button" }
---

# Fugee — Design System

## 1. Overview

Fugee is an agentic assistant for displaced people, asylum seekers, and refugees. The people who use it are often frightened, exhausted, and making decisions that affect their safety and their family's future. The design exists to lower that fear, not to impress.

**Brand personality.** Fugee behaves like a knowledgeable, compassionate case worker — patient, clear, never rushed, never alarmist. It is competent without being clinical, warm without being saccharine, serious without being bureaucratic.

**Emotional target.** The first feeling should be *relief*: "someone calm is going to help me, and I am in control here." Every screen should reduce cognitive load and reinforce safety, privacy, and agency.

**Design philosophy.**
- **Calm over clever.** Generous whitespace, one clear action per moment, no visual noise.
- **Human, not corporate.** A warm off-white canvas and a humanist serif for the name give it the feeling of a trusted organisation (think Médecins Sans Frontières), and the structure and clarity of a thoughtful tool (think Notion).
- **Transparency builds trust.** The agent shows its reasoning rather than hiding behind spinners. Nothing about the person's situation is treated as a secret the machine keeps.
- **Dignity in every detail.** Copy is plain and respectful. The person is "you," never "the applicant" or "the case."

**What to avoid.**
- Corporate/government blue, harsh pure white (`#FFF` as the page background), and clinical gray UI.
- Startup tropes: neon gradients, glassmorphism, oversized rounded everything, emoji as decoration.
- Chatbot-generic patterns: a lone text box, bouncing 3-dot avatars as the whole personality, dark mode "AI" aesthetics.
- Anything that feels like a form to be failed. Fugee guides; it does not gate.

---

## 2. Colors

Color carries meaning here; it is never decorative for its own sake.

- **Primary — Deep teal-green `#0E6A58`.** The voice of Fugee. Used for the agent, primary structure (avatars, progress, the roadmap spine), and trust signals. Teal-green reads as safety, growth, and steadiness without the cold authority of corporate blue. `primary-deep #0A5042` is its shadow/pressed companion and the color for text sitting on a teal tint. `primary-tint #E5EFEA` is the agent's "breath" — agent message bubbles, hovers, and quiet surfaces.
- **Secondary — `#2E7D6C`.** A lighter supporting teal used only in gradients (e.g. the assessment progress bar) and subtle accents. Never competes with primary for attention.
- **Accent — Warm amber `#E07B39`.** The single call-to-action color and the color of *the person* (user message bubbles, their selections). Amber is human warmth and forward motion — a lantern, not an alarm. Reserve it for the one thing you want the person to do next, and for representing the user's own voice. `accent-deep #C26329` handles hover/pressed and the solid drop-shadow under primary buttons. `accent-tint #FBEDE1` fills user bubbles and gentle highlights.
- **Background — `#F7F5F0`.** Warm off-white, like paper. It makes the whole product feel calmer and more human than stark white and reduces glare for tired eyes.
- **Surfaces — `#FFFFFF` / `#FCFBF7`.** White for primary cards and screens; the warmer `surface-2` for nested panels, footers, and the "facts" sidebar so layering reads without heavy borders.
- **Text — `#1A1A1A` body, `#51596A` secondary, `#6B7280` muted.** Near-black (not pure black) for comfortable reading on warm paper. Secondary slate for supporting sentences; muted gray only for labels, captions, and metadata.
- **Semantic — success `#2C8A59`, warning `#B5841C`, danger `#BE3F2C`.** Success marks completed checklist items and strong country matches. Warning marks a "moderate" match or a caution. Danger is for genuine errors only and should rarely appear — this product must never feel like it is scolding someone.

**Contrast rule.** All text must meet WCAG AA against its actual background. Muted gray (`#6B7280`) is reserved for small non-essential labels; never use it for primary reading content on the warm background.

---

## 3. Typography

Two families, each with a clear job.

- **Fraunces (display serif)** — the app name, page/section headings, country names, and document titles. Its soft, slightly old-style character is what makes Fugee feel human and institutional-in-a-good-way rather than like an app. Use it at weight 600 for headings, with tight tracking on large sizes.
- **Inter (UI sans)** — everything else: body copy, messages, labels, buttons, data. Chosen for its calm, highly legible letterforms at small sizes and across many languages/scripts.

**Hierarchy & when to use it.**
- `h1` (38–58px Fraunces 600): the welcome wordmark only — one per product moment.
- `h2` (28px Fraunces 600): screen-level titles where present.
- `h3` (20px Fraunces 600): card titles ("Your roadmap"), country names, document headings. *Exception:* short structural labels like the facts-panel heading use Inter 700 at 15px so the serif stays reserved for content with weight.
- `body-lg` (18px): the tagline and lead sentences.
- `body-md` (15px): the default for messages, descriptions, and most copy.
- `body-sm` (13.5px): dense metadata, step descriptions, prep lists.
- `label` (12px Inter 600, uppercase, 0.06em tracking): section eyebrows ("CHOOSE YOUR LANGUAGE", "YOUR ANSWER", phase tags).
- `caption` (12px muted): timestamps, file sizes, helper notes.

**Readability rationale.** Body never drops below ~13.5px. Line-height stays generous (1.55–1.75) because users may be reading in a second or third language, on a phone, under stress. Line length in reading columns is capped (~60–66ch) for comfortable scanning. Use `text-wrap: pretty/balance` on headings and short paragraphs.

---

## 4. Layout

- **Reading width.** Primary reading and single-column phases (Intake, Interview) are centered with a **max content width of 780px**. This keeps text comfortable and the product intimate.
- **Wide phases.** Assessment (Phase 3) and Recommendations/Documents (Phases 4–5) use a responsive **sidebar + main** or **multi-card grid** and may extend to a wider container (up to ~1180px) so two panels or three cards breathe. The reading column inside still respects comfortable measure.
- **Grid.** Phase 3 = `300px | 1fr` (facts | reasoning). Phase 4 country cards = 3-up grid collapsing to 1-up under ~820px. Phase 5 = `1.1fr | 0.9fr` (document preview | checklist & files).
- **Spacing philosophy.** Whitespace is a feature, not waste — it is how the product signals calm. Use the spacing scale (4/8/16/24/40/64). Sections are separated by `xxl` (64px) vertical rhythm and a single hairline divider; never by heavy boxes or color blocks stacked back-to-back.
- **Mobile-first.** Everything must be usable and beautiful at **390px**. Multi-column layouts collapse to a single column; pills wrap; the progress rail hides its text labels and keeps the numbered dots. Touch targets are **never smaller than 44px**. Buttons go full-width on narrow screens.
- **Semantics.** Use `header`, `nav`, `main`, `section`, `article`, `aside`, `dl/dt/dd` for fact lists, and real `button`/`input`/`textarea`/`label` controls. This is a vulnerable-user product — assistive-tech support is not optional.

---

## 5. Elevation & Depth

Depth is **minimal and meaningful**. Fugee is paper-like and flat by default; elevation is used only to lift a true surface (a screen, a menu) off the page, never for decoration.

- `shadow-sm` — `0 1px 2px rgba(13,46,38,.06)`: avatars, small chips, subtle hover lift on files/cards.
- `shadow-md` — `0 6px 20px rgba(13,46,38,.08)`: the main "screen" frames that hold each phase.
- `shadow-lg` — `0 18px 48px rgba(13,46,38,.12)`: only transient overlays such as the open country-selector menu.

Shadows are tinted with the deep teal (not neutral black) so they sit harmoniously on the warm canvas. **Buttons use a 2px solid offset shadow** (e.g. `0 2px 0 accent-deep`) rather than a blur — a tactile, physical "pressable" feel that suits the calm, honest tone. Surface layering (`surface` on `background`, `surface-2` nested inside) does most of the depth work with borders, so blur shadows stay rare.

---

## 6. Shapes

Roundness communicates softness and safety here, applied on a consistent scale.

- `rounded-sm 4px` — small nested elements, focus outlines.
- `rounded-md 8px` — buttons, inputs, document items, inner blocks. The everyday corner.
- `rounded-lg 16px` — screen frames, country cards, large panels. Generous but not bubbly.
- `rounded-full` — pills (language, multiple-choice, badges), progress dots, and avatars. Fully round elements read as friendly and tappable.

**What roundness communicates.** Soft corners lower the institutional, form-like feeling and make the interface approachable. But corners stay *measured* — 16px max on big surfaces — so the product reads as a serious, trustworthy tool, not a toy. Avoid pill-shaping large rectangular cards or over-rounding the document preview, which should feel like a real printable page.

---

## 7. Components

**Buttons.**
- *Primary* (`button-primary`): solid amber, white text, 8px radius, 2px `accent-deep` offset shadow. The single most important action on any screen (Begin, Download all). One primary per view.
- *Secondary* (`button-secondary`): white fill, teal text, hairline border; hover fills with `primary-tint`. For alternative actions (Select this country on non-chosen cards).
- *Ghost* (`button-ghost`): transparent, teal text, used for low-emphasis actions (Save and continue later) — always paired with a leading line-icon.
- *Teal* variant: solid primary with `primary-deep` offset shadow — used for in-flow continue and confirmed/selected states.

**Inputs (`input-field`, textarea).** White surface, 1.5px `primary-tint-2` border, 8px radius. On focus: border becomes `primary` plus a 4px `primary-tint` ring. Placeholders are muted and reassuring ("Take your time…"). Always have a visible focus state.

**Phase pill / progress rail (`phase-pill`).** A horizontal row of numbered 22px dots joined by short hairlines. *Done* = filled teal dot with a white check, secondary-color label. *Active* = filled amber dot with a 4px `accent-tint` halo and a bold, full-strength label. *Upcoming* = white dot, `line-strong` border, muted number. On mobile, hide the text and keep the dots. Order for the interview: Intake → Situation → History → Goals → Review.

**Messages (`message-agent`, `message-user`).** Agent messages sit left with a 34px teal avatar bearing the white Fugee mark; bubble is `primary-tint` with a 5px-flattened bottom-left corner. User messages sit right with an amber avatar; bubble is `accent-tint` with a flattened bottom-right corner. The *current* agent question is a white bubble with a teal-tint border and `shadow-sm` so it stands out as "this is what we're answering now." A `thinking` indicator (three teal dots, gentle blink) plus a short reassuring phrase ("Fugee is listening") communicates streaming — never a spinner.

**Structured responder.** Below the current question, the answer control adapts to the question via a small segmented switch (Choice / Country / Free text):
- *Multiple-choice pills* — round, single- or multi-select; selected pill fills teal with a leading check. Comfortable 44px tap height.
- *Country selector* — a search input with a leading pin icon and an open `shadow-lg` menu of flag + name rows; the highlighted/origin row is tinted teal.
- *Free text* — a generous textarea with a calm, multilingual-friendly placeholder.

**Country card (`country-card`).** Flag + Fraunces name + a match badge (`badge--strong` success-tint / `badge--moderate` warning-tint). A bordered facts block (processing time, UNHCR office, acceptance for this profile, primary language), an expandable "What you need to prepare" (`<details>`), and a select button. The chosen card gets a `primary` border, a 3px `primary-tint` ring, white fill, and its button switches to the teal "✓ Selected" state.

**Roadmap.** A vertical numbered timeline: 42px teal numbered nodes connected by a `primary-tint-2` spine. Each step has an Inter-700 title, a plain-language description, and small "tag" chips for *who to contact* (with a teal pin icon) and *estimated time* (clock). The roadmap header names the selected country and notes it updates on change.

**Language pill (`language-pill`).** Round, white, hairline border; shows the language in its own script with a small romanized gloss. Selected = filled teal. Used in the intake grid; wraps freely.

**Document item (`document-item`).** A row with a 38px `primary-tint` file-type icon, a bold title + muted meta line (format, pages, languages), and a 38px download button that fills teal on hover. **Checklist items** use a custom 22px checkbox that fills `success` with a white check when ticked; checked rows mute and strike their label. **Document preview** is a white, page-like card with a soft bottom fade; interview-derived values are highlighted with an `accent-tint` "fill" mark to show what Fugee pre-filled.

**Trust note.** A small rounded-full chip with a lock glyph reaffirming privacy. Quiet, persistent, never a modal.

---

## 8. Do's and Don'ts

**Do**
- Keep one clear primary action (amber) per screen; everything else is secondary or ghost.
- Use teal for *Fugee's* voice and structure, amber for *the person* and their next step.
- Show the agent's reasoning openly; prefer a written, progressive "document being thought through" over spinners.
- Address the person as "you," in plain, respectful, reassuring language. Offer "Save and continue later" wherever the journey is long.
- Let layouts breathe — honor the spacing scale and the 64px section rhythm.
- Provide the right input control for each question (pills, country search, or free text), not a single text box.
- Maintain WCAG AA contrast, visible focus rings on every control, and 44px minimum touch targets.
- Tint shadows with deep teal; keep elevation minimal and purposeful.
- Render content in the person's chosen language and script; design components to tolerate long words and RTL text.

**Don't**
- Don't introduce corporate blue, pure-white page backgrounds, or a clinical gray UI.
- Don't use gradients as decoration, glassmorphism, or heavy drop shadows. (A subtle teal→secondary gradient on the assessment progress bar is the only sanctioned gradient.)
- Don't use emoji as decoration; the only emoji permitted are country flags as functional identifiers.
- Don't over-round large cards or pill-shape the document preview — it should read as a real page.
- Don't hide the agent behind a loading spinner or surface raw model/system jargon.
- Don't crowd screens or stack multiple primary (amber) actions.
- Don't use red/danger except for genuine errors; never make the person feel they have failed a form.
- Don't shrink body text below ~13.5px or drop line-height below 1.5.
- Don't store or imply storage of personal information without explicit, visible consent.
