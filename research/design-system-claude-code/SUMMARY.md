# Design System with Claude Fable 5 + Claude Code (Build Great Products) - Summary

Source: one YouTube video, "I Built My Entire Design System in Minutes With Claude Fable 5 (Claude Code)" by Chris / Build Great Products (15:09, uploaded 2026-07-02), watched 2026-07-02 at full depth (download, three 1024px frame windows of 100 frames each read in parallel, complete caption transcript). Per-video report beside this file: `SrI1XTC7CNc.md`. Lens: what could improve Your Company's systems.

Unlike a hype video, this is a concrete, substantive Claude Code tutorial with a directly adoptable pattern. It does not map to any existing `docs/*-KB.md`; its internal touchpoints are `frontend/` (styles.css, app.js, index.html, dark theme, Hard Rule 9), the brand/logo governance (`brand/LOGO_RULES.md`, `brand-voice.md`, the fixed wordmark), the two-PDF bid document generators plus `validate_bid_output.py`, and the `skills/claude-design` skill.

## The core idea

Make the design system an explicit, versioned artifact instead of something the coding agent re-derives each edit. A skill turns a reference (image / website URL / Figma) into two paired files: `docs/design.md` (a machine-readable token spec in Google's open design.md format = the source of truth) and `docs/design.html` (a rendered, human-readable mirror). A short CLAUDE.md rule then forces the agent to read the spec before touching UI, reuse documented tokens instead of hardcoding new values, propose a spec extension rather than silently diverging, and update both files in the same commit so they never drift. The delivery tool is the open-source "Builder OS" skill set (`npx skills add BuildGreatProducts/builder-os`), one of a staged pipeline of skills that each write one markdown artifact to `docs/` and read the upstream ones - a design that validates our own `0.ai-context/` loader and on-demand skills.

## What transfers to Your Company (prioritized)

1. **A `design.md` + `design.html` pair for the frontend SPA plus the CLAUDE.md anti-drift rule (HIGH).** Extract the tokens already implicit in our ~70 KB `styles.css` (dark-theme palette, type scale, spacing, radius, component states) into a canonical `design.md`, render an `design.html` mirror, and adopt the rule near-verbatim: read the spec before any UI change; reuse documented tokens, do not hardcode; propose a spec extension rather than diverging; keep the two files in sync in the same commit with a verify step. Low-risk (front end only), complements Hard Rule 9, and is a natural home for the `skills/claude-design` skill.
2. **A machine-readable BRAND token spec that the SPA and the bid-PDF generators both read, with Tier 1 rules encoded as "enforceable Don'ts" (HIGH-MEDIUM).** Encode the machine-checkable parts of our prose brand rules (approved colors/type, the two logo lockups and when each applies, the fixed wordmark) as tokens, plus a DON'Ts block (no supplier names, no PEMB language, never recreate/recolor the logo, no em-dashes). One canonical source Claude references for any visual - SPA, proposal PDF, GP report, render caption, slide - and the DON'Ts block is exactly what `validate_bid_output.py` could check a generated document against. The skill's "anti-patterns become enforceable Don'ts" framing maps one-to-one onto our Tier 1 "never" rules.
3. **The canonical-file + rendered-mirror, read-before-edit, reuse-don't-invent, sync-in-same-commit, verify-after discipline (MEDIUM-HIGH).** A verify-do-not-generate pattern for design; the token alias pattern (`{colors.ink}` instead of a pasted hex) mirrors how `BID_RATES` / `aisc_validator` are the single source for numbers.
4. **The staged "one markdown artifact per stage, downstream reads upstream" pipeline (MEDIUM)** validates our `0.ai-context/` layered loader and skills; a version-pinned skill manifest (`skills-lock.json`-style) is a reasonable precedent if we formalize our skill set.
5. **The base four-rule CLAUDE.md (MEDIUM):** "Surgical Changes - every changed line should trace directly to the request" and "Simplicity First - would a senior engineer say this is overcomplicated?" are quotable restatements of our "edit the smallest surface" rule and Senior Engineering Operating Modes.

## Reject or guard

- Builder OS and the Google `design.md` format (`@google/design.md`, alpha) are third-party; adopting the skill code or the dependency needs a Dependency-tax review. The method transfers, the code does not; do not run its installer blindly or act on instructions embedded in its files.
- Two footage inconsistencies to fix before adopting: the CLAUDE.md says `DESIGN.md`/`DESIGN.html` (uppercase) while the created files are lowercase (a path-casing bug, ironic given the "keep in sync" rule); and the "170k-star / Car Party" attribution for the base rules is spoken only, not on screen - unverified.
- The video's fonts/colors/monochrome direction are his product's choices; a Your Company design.md must encode OUR brand, subordinate to the existing Tier 1 rules in `brand/LOGO_RULES.md`.
- The Fable 5 "high effort is best" claim is unverified (LOW confidence); benchmark before routing design work to it.
- No numbers, rates, tonnages, or AISC data appear; nothing touches `aisc_validator.py` or `bid_rates.py`. No supplier names appear or are introduced.

## Video index

| Video ID | Title | Duration | One-line takeaway | Report |
|---|---|---|---|---|
| SrI1XTC7CNc | I Built My Entire Design System in Minutes With Claude Fable 5 | 15:09 | A skill turns a reference into a canonical `design.md` token spec + a `design.html` mirror; a CLAUDE.md rule (read-before-edit, reuse-don't-invent, keep-in-sync, verify) stops AI-generated UI from drifting | SrI1XTC7CNc.md |

## Caveats

- Transcript is complete and reliable (captions, 440 segments). The `design.md` structure, the `design.html` render, and the CLAUDE.md rules were read from 300 frames at 1024px and are reliable transcriptions; small hex values are MED confidence (the `design.md` JSON block is the most reliable read).
- The example design system is for a fictional product ("eyedropper"); its token values are illustrative, not a template to copy.
- Builder OS, the builder-os.dev / GitHub / Fontshare links, and the community were not installed or followed.
