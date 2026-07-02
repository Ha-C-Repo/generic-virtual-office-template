# Site Diary - Claude Code Handoff (Track B)

**Date:** 2026-06-10
**From:** Cowork (per SITE_DIARY_HANDOFF_v1.1.md section 9)
**Track:** B confirmed by Owner 2026-06-10. No WhatsApp number.
**Login:** Supabase, same pattern as the training portal. Crew register
with the shared signup code on index.html, then use diary.html.

## Voice rules (apply to all code, comments, and docs)

No em-dashes anywhere. Hyphens or periods only. Short sentences.
Specific numbers. No filler words.

## What exists already (Cowork built, sandbox)

- `Site Diary/sandbox/whatsapp_parser.py` - export parser, 12h and 24h
  formats, multiline, media markers, sha1 msg_id dedupe. 16 locked tests
  in `test_parser.py`, all passing. Treat as reference implementation;
  port logic, do not regress behavior.
- `Site Diary/sandbox/appsscript/Code.gs` - web app backend draft:
  doPost entry ingestion with dedupe, Drive uploads (Photos, Voice
  Notes subfolders), doGet pending-approval feed, approve action,
  ERRORS tab logging, shared-secret check.
- `Site Diary/sandbox/diary.html` - mobile-first page draft. Supabase
  session gate reusing the portal config.js, MCA palette, entry form
  (project, date, weather, free text, photos, voice note), approval box.
- `Site Diary/sandbox/NC_Site_Diary_SANDBOX.xlsx` - schema staging with
  COST_CODES seed.

## Your build list

1. **Sandbox Google Sheet.** Create "NC Site Diary SANDBOX" in the
   Workspace Drive. Tabs and columns exactly per section 7 below. Seed
   COST_CODES from the staging xlsx (6 codes: FAB ton 11 budget_hours,
   ERECT ton, DECK SF, DETAIL sheet, MOB LS, PUNCH hr). Record the sheet
   id HERE: `SANDBOX_SHEET_ID = 1ozkhJTNF9FF3tSpjzOQuBu6ooeL7G8lgfnRLQplgoM0` (logged by setupSandbox 2026-06-10 8:18 PM; DRIVE_FOLDER = 1uIdFEujurhdrRvsAiBPP19itClGTPryf). Reference baselines:
   fab 11 hr/ton, shop rate $145/hr (internal, never client-facing).
   2026-06-10 status: this PC holds no Google credential (checked: no
   clasp auth, no Drive mount, no Workspace connection in any MCP
   tool), so sheet creation is scripted instead of done live. Run
   `setupSandbox()` once per `sandbox/appsscript/DEPLOY.md`. It builds
   the sheet, tabs, seed, Drive folders, and secret in one run and logs
   the id. Paste the logged id over the blank above. Tab and header
   exactness is locked by `sandbox/appsscript/test/run_tests.js`, which
   checks Setup.gs output against a hard-coded copy of section 7.
2. **Apps Script project.** clasp-ready. Files: Code.gs (start from the
   draft), appsscript.json (V8, webapp executeAs USER_DEPLOYING, access
   ANYONE_ANONYMOUS). Script properties: SHEET_ID (sandbox id), 
   SHARED_SECRET (generate 32+ chars), DRIVE_FOLDER (create
   /Site Diary with Photos, Voice Notes, Chat Exports subfolders).
   Harden the draft: size-cap uploads at 25 MB, reject non-image
   non-audio MIME types, LockService around appendRow to prevent
   concurrent duplicate writes.
3. **diary.html + diary.js.** Finish from the draft. Split inline JS
   into diary.js to match portal file conventions. Add the EXEC_URL and
   SECRET at deploy time, never committed in plaintext to a public
   repo (the portal repo is private; still keep the secret in one
   place). Project dropdown reads from a PROJECTS constant for now;
   pilot entry is "Genius Kids STEM Academy (Katy)".
   Constraints: NEW files only in Ha-C-Repo/yourco-training-portal.
   Do not modify index.html, portal.js, suite.html, config.js, or any
   module page. Do not use #1e3a8a, #1d4ed8, or #93c5fd.
4. **Parser port.** If RAW_MESSAGES export ingestion runs inside Apps
   Script, port whatsapp_parser.py logic to GS keeping the msg_id
   algorithm identical (sha1 of timestamp|sender|body, first 16 hex,
   exp- prefix). Otherwise the Python tool stays the official path and
   Cowork runs it.

## Section 7 schema (verbatim)

| Tab | Columns |
|---|---|
| RAW_MESSAGES | msg_id, timestamp, source (api/portal/export), chat_name_or_user, sender, body, media_link, processed |
| DIARY | date, project, supervisor, weather, work_summary, safety_notes, photos_link, approved, approved_ts |
| LABOR | date, project, employee, hours, cost_code |
| QUANTITIES | date, project, cost_code, qty, unit |
| DELIVERIES | date, project, supplier_internal, item, docket_link |
| DELAYS | date, project, type (weather/site/client), hours_lost, notes |
| TASKS | created, project, task, owner, due, status, source_msg_id |
| COST_CODES | code, activity, unit, budget_qty, budget_hours |

Plus an ERRORS tab (timestamp, error) created by Code.gs on demand.

## Acceptance tests (two-step verification gate)

Step 1, sandbox functional:
- [x] Form submit from a phone writes exactly 1 RAW_MESSAGES row with
      source=portal, correct sender email, ISO timestamp. (2026-06-11
      iPhone Safari: portal-7ccca108, owner@yourcompany.example.com, photo
      IMG_2958.png in /Photos with media_link.)
- [x] Resubmitting the identical entry produces zero new rows (dedupe).
      (2026-06-11 desktop: page showed "Already logged this entry. No
      duplicate made.", sheet has exactly 1 ENTRY A row.)
- [x] Photo upload lands in /Site Diary/Photos and the Drive URL appears
      in media_link. (2026-06-11 desktop: site_diary_test_photo.jpg in
      Photos, drive.google.com link in row 4 media_link.)
- [ ] Voice note lands in /Site Diary/Voice Notes.
- [x] Wrong secret gets {ok:false} and writes nothing. (2026-06-11:
      {"ok":false,"error":"denied"}, zero rows.)
- [x] Unauthenticated visit to diary.html shows the sign-in gate, no form.
      (2026-06-11 desktop, localhost serve.)
- [x] `pending` feed returns the latest unapproved DIARY row for that
      supervisor only. (2026-06-11: approval box showed the seeded
      owner@yourcompany.example.com row.)
- [x] Approve sets approved=TRUE and approved_ts on the right row.
      (2026-06-11: H2=TRUE, I2=2026-06-11T15:38:07.273Z.)
- [x] Parser tests: all 16 pass unmodified. (2026-06-10, also verified
      SAMPLE_GeniusKids_chat.txt parses to an exact match of the
      processed SAMPLE_RAW_MESSAGES.csv, 11 rows, all 8 fields, zero
      new rows on re-ingest.)
- [x] Page loads and signs in via the shared Supabase session from the
      training portal (config.js), then submits on a phone browser.
      (2026-06-11 iPhone Safari over office Wi-Fi, localhost serve at
      10.1.10.109:8080.)
      [line reconstructed 2026-06-11 after a mount write-race truncated
      this file at "Page loads and s"; truncated copy backed up to
      _handoff/backups/2026-06-11T01-40-00Z_handoff_truncated/]

Step 2, Owner sign-off: nothing ships to the live sheet, portal,
or website until every Step 1 box is checked on sandbox cop