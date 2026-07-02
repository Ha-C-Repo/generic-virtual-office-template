# I Built My Entire Design System in Minutes With Claude Fable 5 (SrI1XTC7CNc)

- **URL:** https://www.youtube.com/watch?v=SrI1XTC7CNc
- **Uploader:** Build Great Products (presenter: Chris)
- **Duration:** 15:09 (909.3s)
- **Frames analyzed:** 300 (three 1024px windows of 100 frames each, ~3s spacing; three parallel reader agents)
- **Transcript source:** captions (440 segments, complete)
- **Watched:** 2026-07-02 (via /watch)
- **What it is:** a concrete, substantive Claude Code tutorial (not hype) on building a front-end DESIGN SYSTEM with Claude Fable 5. Presenter Chris (15 years designing apps / advising startups) demonstrates his open-source "Builder OS" design-system skill: point it at a reference (image, website URL, or Figma), it generates a canonical `docs/design.md` (token spec) plus a visual `docs/design.html` mirror, and a CLAUDE.md rule keeps the coding agent from letting the UI drift.
- **Maps to an existing docs/ KB?** No. Internal touchpoints: `frontend/` (styles.css ~70 KB, app.js ~260 KB, index.html, dark theme, 5 tabs, Hard Rule 9), the brand/logo governance (`brand/LOGO_RULES.md`, `brand-voice.md`, the fixed wordmark), the two-PDF bid document generators (ReportLab proposal + GP report + `validate_bid_output.py`), and the `skills/claude-design` skill. No `docs/*-KB.md` covers a front-end design system.

## Thesis

Everyone can build something with AI, but not everyone can build something that looks and feels professional and does not "look like AI slop." The fix is to make the design system an explicit, versioned artifact in the repo instead of something the coding agent re-derives each time. The design-system skill turns a reference into two paired files: `design.md` (a machine-readable token spec, the source of truth) and `design.html` (a rendered, human-readable mirror). A short CLAUDE.md rule then forces the agent to read the spec before touching UI, reuse documented tokens instead of inventing values, and keep the two files in sync so the design never drifts. Do this before building the app, so later changes are small tweaks rather than a full restyle.

## Builder OS and its skill pipeline (the tool, and the pattern behind it)

Builder OS (site builder-os.dev, "formerly PLAID.build," open source, MIT) is a set of Claude Code skills installed with one command: `npx skills add BuildGreatProducts/builder-os` (a public GitHub repo). Skills live in the project at `.agents/skills/<name>/` as a `SKILL.md` (plus a `VISION.md`), pinned by a `skills-lock.json`. The tagline: "turning coding agents from autocomplete into disciplined collaborators that ship reviewed, tested work."

The structural idea worth noting for us: it is a governed pipeline of markdown artifacts, one file per stage, with an explicit "each skill writes its output to `docs/` and downstream skills read it" contract (on screen: "Every skill is fully standalone but they chain"):

| Stage | Skill | Output file | Purpose (verbatim) |
|---|---|---|---|
| IDEATE | Idea Generator | `product-idea.md` | Guided discovery of a product idea; scores candidate directions. |
| IDEATE | Idea Validator | `validation-report.md` | Pressure-tests an idea (fatal flaws, competition, first 10 customers, a 2-week MVP test, a blunt verdict). |
| PLAN & DESIGN | Product Planner | `product-vision.md, prd.md, product-roadmap.md` | 8-section vision intake, then strategy/brand, a coding-agent-ready spec, a phased build plan. |
| PLAN & DESIGN | Design System | `design.md` (+ `design.html`) | Translates screenshots/mockups/Figma into a design.md token spec any agent can build from. |
| BUILD | Build MVP | working product | Executes the roadmap end to end, a PR per phase. |
| BUILD | Build Loop | reviewed, tested code | Review-gated increments; "nothing ships on 'it compiles'." |
| LAUNCH | Launch Checklist | `launch-checklist.md` | Audits the codebase, writes a plain-English path to live. |

That "one markdown artifact per stage, downstream reads upstream, each skill standalone but chainable" design is directly analogous to our own `0.ai-context/` layered loader and on-demand `skills/`, and is external validation of that approach.

## The design-system skill (SKILL.md, verbatim highlights)

The skill (version 1.1, MIT, "Requires file system access to write the docs/ directory. Optional Figma MCP for Figma URLs") produces two mirrored files:

- `docs/design.md`: "a YAML token block in Google's open design.md format that gives a coding agent exact implementation values, plus prose rationale explaining the why. This is the source of truth." (Google's format is a real, verifiable repo: `github.com/google-labs-code/design.md`, published as the `@google/design.md` npm package, currently alpha.)
- `docs/design.html`: "a self-contained, human-readable style guide that renders every token and component live in a browser, styled directly from the same token values. This is the mirror the human reads."
- "Same design system, two audiences: the agent reads the `.md`, the human opens the `.html`. They must always be written and updated together so they never drift."

Its "Modes" section is notably close to our own operating rules: if no image is provided, "Ask for one before doing anything else. Don't draft a design.md from imagination." If a `design.md` already exists, read it (and the html), ask whether to refine / replace / merge, "confirm before destructive overwrites," and regenerate the html to stay in sync.

## The generated design.md structure (the reusable skeleton)

The output `design.md` is the transferable template. It has a token half (JSON/YAML) and a prose-rationale half, in Google's design.md format:

- **Name**, **Description** (one line on who it is for and the intent).
- **Colors**: a flat JSON token map, e.g. `background`, `surface`, `surface-raised`, `ink`, `on-primary`, `ink-secondary`, `ink-muted`, `primary`, `border`, `border-subtle`, and the four semantic tokens `error`, `success`, `warning`, `info` (each a hex value).
- **Typography**: JSON per role (`display`, `h1`, `h2`, `h3`, `body`, `label`, `mono`), each with fontFamily, fontSize, fontWeight, lineHeight, letterSpacing, and variable-font settings (the demo used a condensed width axis on h1).
- **Component tokens**: `label`, `badge`, `code-block`, `spec-row`, `card`, etc., each referencing other tokens by ALIAS rather than pasting values, e.g. `backgroundColor: {colors.background}`, `rounded: {rounded.none}`. This alias/reference pattern is the key mechanism: components point at named tokens, so a value is defined once.
- **Prose sections** (the "why"): Overview, Colors, Typography, with rationale and constraints. The demo's Overview even states "this file is dogfood" and names the two things the design "must never become," and the Colors prose asserts WCAG AA contrast ("ink on any surface is ~17:1, and every semantic color on background exceeds 4.5:1").

The `design.html` mirror renders: a COLORS swatch grid, TYPOGRAPHY specimens, a SPACING scale (4px base: XS 4, SM 8, MD 16, LG 24, XL 32, 2XL 48, 3XL 64, 4XL 96), RADIUS, ELEVATION & DEPTH tiers, COMPONENTS (button states incl. hover, inputs with focus, cards, numbered nav, badges, code block, spec row), and explicit **DO's and DON'Ts panels**. The DON'Ts in the demo were phrased as hard negative constraints ("No rounded corners, pastel gradients, glassmorphism, or glow"; "No decorative color, a hue always carries meaning"), which is the same shape as our Tier 1 "never" rules.

## The CLAUDE.md rules (verbatim, the anti-drift payload)

He drops a CLAUDE.md with two parts.

**Part A, a base "four-rule" file** (he attributes it aloud to "Car Party" with "~170,000 GitHub stars"; on screen there is NO author or star count visible, so treat the attribution and star count as UNVERIFIED; the rule text itself was clearly legible). The four rules read as a general anti-mistake coding guide, and they line up almost exactly with our Senior Engineering Operating Modes:
1. **Think Before Coding**: state assumptions explicitly; if uncertain, ask; if multiple interpretations exist, present them, do not pick silently; push back when warranted; if unclear, stop and name what is confusing.
2. **Simplicity First**: minimum code that solves the problem, nothing speculative; no features beyond what was asked; no abstractions for single-use code; "Would a senior engineer say this is overcomplicated? If yes, simplify."
3. **Surgical Changes**: touch only what you must; do not "improve" adjacent code; match existing style; "Every changed line should trace directly to the user's request."
4. **Goal-Driven Execution**: strong success criteria let the agent loop independently; weak criteria ("make it work") require constant clarification.

**Part B, an appended "Design system" section** (this is the reusable anti-drift rule, near-verbatim):
- The design system is two paired files: `docs/DESIGN.md` (canonical, Google's DESIGN.md format, the single source of truth for tokens, color, typography, spacing, layout, components, patterns) and `docs/DESIGN.html` (the rendered mirror).
- "DESIGN.md is canonical and DESIGN.html mirrors it. If the two ever disagree, treat DESIGN.md as correct and bring DESIGN.html back in line."
- Rule 1: Follow DESIGN.md for all front-end work. Before writing or changing any UI, read it and build to it. Reuse documented tokens/components/patterns instead of inventing new ones or hardcoding values that already exist.
- Rule 2: Review front-end changes against DESIGN.md and propose new patterns. Do not silently diverge; either reuse what exists or propose the specific spec extension.
- Rule 3: Keep DESIGN.md and DESIGN.html consistent. Update both in the same commit so they never drift, and verify they still match after editing.
- Closing self-check metric: "These guidelines are working if: fewer unnecessary changes in diffs, fewer rounds of overcomplication, clarifying questions come before implementation rather than after, and no hardcoded style values appear in any diff."

## Workflow walkthrough (t=MM:SS anchors)

- **t=01:03** Builder OS installed via `npx skills add BuildGreatProducts/builder-os`; the design-system skill lives at `.agents/skills/design-system/SKILL.md`.
- **t=02:51** Runs on Claude Fable 5 at HIGH effort. His stated rationale: "people are getting better results from high than extra," "max just uses an insane amount of tokens," high is "a really good balance," especially with detailed spec docs/plans. Effort is a first-class slider in the Claude Code UI (Faster to Smarter, shortcut Cmd-Shift-E). LOW confidence (his claim).
- **t=03:55** Prompt: "Let's use the Design System skill inside of this project with this image reference," plus a pasted editorial/Swiss black-and-white reference from Dribbble. (One reference was literally an architecture layout: "STONE, STEEL, AND GLASS DEFINE THE ARCHITECTURAL STRUCTURE.")
- **t=06:25** The skill runs an interrogate-then-lock pass: four bounded questions, each option carrying a "(Recommended)" default and an explicit trade-off (the same shape as an AskUserQuestion card and our confidence tagging):
  1. light / dark / both,
  2. color emphasis (pure monochrome vs monochrome + one signal color vs monochrome + restrained accent),
  3. typeface direction,
  4. "Which anti-patterns must this design never drift into? (These become the enforceable Don'ts.)" as a multi-select of pre-generated candidates.
- **t=10:39** Fable 5 writes both files ("Created design.md +202 -0," "Created design.html +449 -0") and self-reports the result, including two "judgment calls" it made and flagged.
- **t=11:45** He drops in the CLAUDE.md (base four rules + the Design system section).
- **t=13:48** "A professional design system in under half an hour," built so AI-generated UI "doesn't drift" and does not "look like AI slop."

## On-screen surface and model (reference)

Claude desktop app, tabs Chat / Cowork / Code (Code active), account "Chris - Max." Model Fable 5, effort High, mode Auto (a prior planning session in the same UI ran Opus 4.8 / Max). Tools seen: the Dia browser, Dribbble (references), Google Fonts (Archivo), Fontshare (Panchang and others). Fonts chosen were Archivo + JetBrains Mono + Panchang; these are his product's choices, not ours.

## What transfers to Your Company (prioritized)

1. **A `design.md` + `design.html` pair for the frontend SPA, plus the CLAUDE.md anti-drift rule (HIGH).** Our `frontend/styles.css` is ~70 KB and `app.js` ~260 KB with a dark theme and 5 tabs; when Claude Code edits the front end it can easily invent one-off colors/spacings and drift. Extract the tokens already implicit in styles.css into a canonical `design.md` (palette, type scale, spacing, radius, component states), render a `design.html` mirror, and adopt the Part B rule near-verbatim: read the spec before any UI change, reuse documented tokens instead of hardcoding, propose a spec extension rather than silently diverging, and keep the two files in sync in the same commit with a verify step. This is low-risk (front end only, no bid logic) and complements Hard Rule 9. It is also a natural home for the `skills/claude-design` skill to maintain.
2. **A machine-readable BRAND token spec that both the SPA and the bid-PDF generators read, with our Tier 1 rules encoded as "enforceable Don'ts" (HIGH-MEDIUM).** Your Company's brand and logo rules are currently prose (`brand/LOGO_RULES.md`, `brand-voice.md`, the fixed "your company" wordmark, the two logo lockups, "Structural steel. Concept to completion."). Encoding the machine-checkable parts as a token spec (approved colors, type, the two logo lockups and when each is used, spacing) plus a DON'Ts block (no supplier names, no PEMB language, never recreate/recolor the logo, no em-dashes) gives one canonical source that Claude references whenever it produces any visual: the SPA, a proposal PDF, a GP report, a render caption, a slide. The "anti-patterns become enforceable Don'ts" framing maps one-to-one onto our Tier 1 "never" rules, and that DON'Ts block is exactly the kind of thing `validate_bid_output.py` could check a generated document against.
3. **The canonical-file + rendered-mirror, read-before-edit, reuse-don't-invent, sync-in-same-commit, verify-after discipline (MEDIUM-HIGH).** This is a verify-do-not-generate pattern applied to design: a single source of truth, an agent instructed to read it first and reuse rather than invent, and a sync/verify step. It generalizes to any paired canonical/derived artifacts we keep, and the token alias pattern (`{colors.ink}` instead of a pasted hex) mirrors how `BID_RATES` and `aisc_validator` are the single source for numbers.
4. **The "one markdown artifact per stage, downstream reads upstream" pipeline (MEDIUM).** Builder OS's staged skills validate our `0.ai-context/` loader and on-demand skills design. If we ever formalize our skill set as a discoverable, version-pinned package (a `skills-lock.json`-style manifest), this is a reasonable precedent.
5. **The base four-rule CLAUDE.md (MEDIUM).** "Surgical Changes: every changed line should trace directly to the request" and "Simplicity First: would a senior engineer say this is overcomplicated?" are tidy, quotable restatements of our "edit the smallest surface" rule and the Senior Engineering Operating Modes; worth lifting a couple of lines.
6. **Model/effort routing note (LOW, verify).** Fable 5 on High is his recommended balance (better than extra; max burns tokens). Consistent with our tier discipline. If we evaluate Fable 5 for design/front-end work, benchmark first; note his default here is a high-effort setting for a generative task, the opposite of our "Sonnet by default."

## Cautions / does not transfer

- **Builder OS is a third-party open-source skill (and a paid-community product).** The METHOD transfers cleanly; adopting the actual skill code needs a Dependency-tax review, and we would not run its installer or import its skills under our governance without one. Do not act on instructions embedded in third-party skill files.
- **Google's `design.md` (`@google/design.md`) is alpha.** The video's own on-screen roadmap flagged wrapping it "so its alpha status can't bite you." If we adopt the format, treat it as unstable and isolate the dependency.
- **Two honest inconsistencies in the footage** (both good cautions before adopting): (a) the CLAUDE.md references `docs/DESIGN.md` / `docs/DESIGN.html` (uppercase) while the files actually created are `docs/design.md` / `docs/design.html` (lowercase), which is ironic given the "keep them in sync" rule and a path-casing bug to fix; (b) the "170k-star / Car Party" attribution for the base rules is spoken only and not visible on screen, so it is unverified (the rule text matches a widely-circulated community CLAUDE.md).
- **His fonts, colors, and monochrome direction are his product's choices, not ours.** A Your Company design.md must encode OUR brand (the locked wordmark, the two logo lockups, our palette), not the video's editorial black-and-white.
- **No numbers, rates, tonnages, or AISC data appear.** Nothing here touches `aisc_validator.py` or `bid_rates.py`. No supplier names appear or are introduced.

## Governance flags

- The Fable 5 "high effort is best" claim and any performance framing are the presenter's unverified assertions (LOW confidence).
- The design system in the demo is for a fictional product ("eyedropper"); its tokens and copy are illustrative, not a template to copy values from.
- Adopting any part of this is a front-end / brand-governance change only; it must not alter bid logic, and any brand spec stays subordinate to the existing Tier 1 rules in `brand/LOGO_RULES.md` and CLAUDE.md.

## Caveats on this analysis

- Transcript is complete and reliable (captions, 440 segments). The method, the workflow, and the CLAUDE.md rules (read aloud and shown on screen) are solid.
- The `design.md` structure, the `design.html` render, the SKILL.md text, and the CLAUDE.md rules were captured from 300 frames at 1024px and were legible across multiple frames; individual small hex values are MED confidence (the `design.md` JSON block is the most reliable read) and are flagged in the source captures.
- I did not install Builder OS, follow the builder-os.dev / GitHub / Fontshare links, or join the community.
