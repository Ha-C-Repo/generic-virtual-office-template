---
name: claude-design
description: Route here when the deliverable is primarily a visual artifact meant to be seen and refined on a canvas - poster, social graphic, infographic, one-pager, slide layout, landing-page or site mockup, UI prototype, logo, brand visual. Drives Anthropic's Claude Design canvas agent through Claude in Chrome (primary) or Windows MCP (fallback). Not for code, formatted documents, bids, live web research, or video.
---

# Claude Design

Claude Design is Anthropic's canvas-based design agent. It gives Claude a visual
canvas plus design tools and iterates on a design through chat. It produces
visual artifacts you refine by looking at them, not code and not formatted text
documents.

## Route here when ALL hold
- The deliverable is primarily a visual artifact meant to be seen: poster,
  social graphic, infographic, one-pager, slide layout, landing-page mockup,
  UI prototype, logo, brand visual.
- The work benefits from a canvas and chat-driven visual iteration.
- The output is not the job of another surface listed below.

Concrete fits in this workspace:
- DOVA: site page mockups and visual concepts before build.
- Pinnacle: advisory one-pagers, pitch visuals, diagram-style explainers for Owner.
- Your Company: marketing graphics, capability one-pagers.

## Route elsewhere (do NOT use Claude Design)
- Code, repos, scripts, app builds: Claude Code.
- Formatted documents (bids, internal -GP analyses, reports, letters): the
  project document skills. Bids stay in the locked Your Company format.
- Live web research: Gemini.
- Video, commercials, reels, brand films: the `Video Creation/` studio (Runway).
- Plain browser or PC automation with no design output: Chrome plus Windows MCP
  directly.

## Access path
1. Chrome (primary): open Claude in Chrome, navigate to the Claude Design
   surface, start or resume a design chat, drive it by prompt.
2. Windows MCP (fallback): only if Chrome cannot load or control the surface.
   Drive the desktop browser or app through Windows MCP.
3. Login gate: if the surface is not authenticated, stop and hand to Joseph.
   State exactly what is needed. Never attempt credentials, account creation, or
   MFA yourself.

## Tier 1 visual rule (Your Company)
Never place MATERIAL_COSTS, supplier names, or margin data in any visual. This is
a Governance Tier 1 line and holds on every Your Company outward graphic. Confirm
the brand before producing anything. Never blend Your Company and Pinnacle in one
deliverable. DOVA is a separate business. Keep the three firewalled.

## Output handling
- When Claude Design produces an accepted artifact, export or download it.
- Place it in the correct project folder (DOVA / Pinnacle / Your Company) using the
  existing naming conventions.
- Hand back to Joseph with the file path and a one-line summary. Do not
  auto-commit.

---
Keep this detail in this skill file. The project CLAUDE.md and the loader point
to this skill by name; do not inline the body.
## App UI token spec (not this skill, but adjacent)

UI work inside `frontend/` (the desktop SPA) is code work and routes to
Claude Code, not Claude Design. Its canonical token spec is `docs/design.md`
with the rendered mirror `docs/design.html` (lowercase). Read the spec before
any `frontend/` UI change; reuse its tokens; keep spec, mirror, and
`frontend/styles.css` in sync in the same commit. Rule of record: the
"Frontend Design Spec" section in CLAUDE.md.
