# Site Diary System - Project Context

**Sponsor:** The Owner
**Handoff:** SITE_DIARY_HANDOFF_v1.1.md (this folder, verbatim archive)
**Phase:** 1 (sandbox) in progress
**Date:** 2026-06-10

## Decisions locked (Owner, 2026-06-10, via Cowork)

1. **Track B.** No clean WhatsApp number. Website portal hub.
2. **Login:** same pattern as the training portal. Supabase email/password
   self-registration with a shared signup code. Field crew register on the
   diary page exactly like trainees register on training.yourcompany.example.com.
3. **Pilot project:** Genius Kids STEM Academy (Katy, TX). GC: Right
   Choice Construction.
4. **Approval channel:** portal page. Supervisor sees yesterday's draft
   diary summary at next login and taps Approve.

## Revised Track B architecture (after studying the training portal)

The handoff assumed Apps Script doGet serves the form with Google-account
or access-code login. The training portal actually runs on Netlify static
pages + Supabase auth (repo Ha-C-Repo/yourco-training-portal, private).
Owner wants diary registration to match the training page. So:

- **Front end:** `diary.html` + `diary.js`, NEW files added to the same
  private portal repo, served by the same Netlify site at
  training.yourcompany.example.com/diary.html. Reuses `config.js` and the Supabase
  session, same signup flow as index.html. Zero edits to any existing
  Regina portal file. Reserved Regina palette (#1e3a8a, #1d4ed8, #93c5fd)
  not used; diary UI uses the MCA public palette (white panels, ink,
  glass teal #2e6e66).
- **Back end:** Google Apps Script web app (doPost only). diary.html POSTs
  the entry JSON (plus base64 photos/voice notes) to the /exec URL with a
  shared secret header. Apps Script appends to RAW_MESSAGES (source:
  portal) and saves uploads to Drive /Site Diary/. This keeps the
  handoff's Sheets schema intact.
- **Approval:** diary.html shows the latest unapproved DIARY row for that
  supervisor (fetched via the same Apps Script, doGet with secret +
  supervisor email) with an Approve button.
- **Site link:** "Site Diary" goes on yourcompany.example.com next to the Team
  Login link, pointing at training.yourcompany.example.com/diary.html. Done at
  Phase 2B go-live, with the Owner's approval, via the normal site deploy.

## Downstream (unchanged from handoff)

One spreadsheet "NC Site Diary", 8 tabs per section 7 of the handoff.
Cowork daily routine = skill `site-diary` (skills/site-diary/SKILL.md).
Weekly digest to Owner. DELAYS is the claims backbone.

## Hard constraints (carried)

- No new paid tools. No unofficial WhatsApp APIs.
- DELIVERIES supplier names are internal only, never exported.
- Sandbox copies first, always. Live sheet and live site untouched until
  the verification gate passes.
- No em-dashes anywhere. Short sentences. Specific numbers.

## Folder map

- `PROJECT.md` - this file
- `SITE_DIARY_HANDOFF_v1.1.md` - the Owner's handoff, verbatim
- `CLAUDE_CODE_HANDOFF.md` - build spec for Claude Code
- `sandbox/whatsapp_parser.py` - Track B optional export parser
- `sandbox/fixtures/` - test exports (12h, 24h, multiline, media omitted)
- `sandbox/test_parser.py` - locked tests
- `sandbox/NC_Site_Diary_SANDBOX.xlsx` - local schema staging + seed
- `sandbox/diary.html` - portal page prototype (sandbox)
- `sandbox/appsscript/Code.gs` - web app backend (clasp-ready)

## Status log

- 2026-06-10: Phase 0 decisions captured. Phase 1 sandbox built: schema
  staged, parser written and tested, diary page prototype drafted,
  Claude Code handoff written. Open: real chat export from the field
  (fixtures are synthetic until one arrives), Google sandbox sheet
  creation (Joseph or Claude Code, IDs go into CLAUDE_CODE_HANDOFF.md).
- 2026-06-10 (Claude Code build): Apps Script project finished and
  hardened (sandbox/appsscript/: Code.gs, Setup.gs with one-run
  setupSandbox() provisioning, appsscript.json, DEPLOY.md, 50-check
  local mock test harness, all passing). diary.html + diary.js written
  as new files on branch site-diary of the portal repo clone
  (training-portal/site), not pushed, Regina files untouched. Parser:
  16/16 locked tests pass; SAMPLE_GeniusKids_chat.txt round-trips to
  an exact match of the processed CSV fixture. Python parser stays the
  official export path (no GS port). Open: one authorized
  setupSandbox() run plus web app deployment (no Google credential on
  this PC), then the phone-side Step 1 boxes against the sandbox.
