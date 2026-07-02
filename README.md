# Generic Virtual Office Template

An industry-agnostic AI "virtual office": a complete operating system for a
small company - bid/estimate procedures, governance gates, skills, brand and
voice rules, and a Windows desktop app - scrubbed of its original company and
ready to be adapted to yours.

Everything company-specific was replaced with placeholders. See SCRUB_REPORT.md
for exactly what was genericized or removed.

## What is in here

- CLAUDE.md - the office operating rules (architecture, hard rules, governance)
- PROJECT_FOLDER_INSTRUCTIONS.md - paste this into your AI workspace (Cowork /
  Claude Project) instructions, then fill in the blanks
- INIT_PROMPT.md - the first prompt to give the AI after you mount this folder
- skills/, .claude/, .specify/, 0.ai-context/ - procedures, governance, loaders
- bridge/, frontend/, main.py, mcp_server.py - the desktop app (Python 3.13 + pywebview)
- docs/, research/ - reference material and knowledge bases
- owner-rules.md, owner-directives-v4.md, company-details.md, rates-and-pricing.md -
  the company rulebook, all values now placeholders
- API Keys/ - placeholder files; add your real keys here (never commit them)

## Setup

1. Clone this repo into the folder your AI workspace will mount.
2. Do a global find for these placeholders and replace with your details:
   "Your Company", "YourCo", "Owner", "The Owner", "yourcompany.example.com",
   "[COMPANY ADDRESS]", "[COMPANY PHONE]", "[CITY, STATE]", "[ISN ID]",
   "[FAB RATE]" and the other bracketed rate tokens.
   (Or skip this step and let the AI do it - see INIT_PROMPT.md.)
3. Fill in your numbers:
   - bridge/bid_rates.py - all values are zeroed with TODO markers
   - rates-and-pricing.md - bracketed rate tokens
   - library/production-rates.yaml - schema kept, values removed
4. Fill in your people:
   - data/core/owner-profile.md - blank template for your principal
   - company-details.md - facts of record
5. Put real keys in API Keys/ (files are named for what they hold). Keep this
   folder out of version control - it is gitignored.
6. App (optional): install Python 3.13, `pip install -r requirements.txt`,
   run `py main.py`. Build an EXE with make_exe.bat.
7. Give your AI the INIT_PROMPT.md contents as its first task. It will walk
   the remaining placeholders with you and adapt the procedures to your industry.

## Notes

- The original industry was structural steel fabrication. Estimating skills and
  reference data (AISC shapes, joist tables) reflect that; keep, adapt, or
  remove them for your industry.
- SCRUB_REPORT.md documents the full scrub and every removed file.
