# Site Diary System. Cowork Handoff v1.1
Date: 2026-06-10
Sponsor: The Owner
Prepared by: Virtual Office session with Joseph
Source: ConstructIQ video "Claude + WhatsApp: The AI Construction Site Diary" (transcript and mindmap on file)
Change from v1.0: added Track B, a website portal hub, as the fallback if a dedicated WhatsApp number is not available.

## 1. Objective
Replicate the video's site diary architecture inside the approved Your Company stack. Capture daily field updates, convert unstructured input to structured rows in Google Sheets, generate a task register, and build the delay/disruption record needed for claims documentation.

## 2. Input hub: two tracks, one decision gate
Track A (preferred if a number is available): WhatsApp Cloud API. Supervisors message a dedicated Your Company WhatsApp Business number. Free for inbound and service-window replies.
Track B (fallback, no number required): website portal hub. A diary entry page behind login, linked from the Your Company site next to the existing training portal. Built as a Google Apps Script web app. Zero hosting cost, writes straight to Sheets.
Decision gate: Owner confirms whether a clean number (not registered on consumer WhatsApp) exists. No number means Track B. Everything downstream of RAW_MESSAGES is identical for both tracks.

## 3. Stack mapping (video tool to Your Company tool)
| Video uses | Your Company uses | Reason |
|---|---|---|
| Airtable | Google Sheets (Workspace Premium) | Airtable is out of stack. Sheets is the established choice for structured databases. |
| Zapier WhatsApp trigger | Track A: Meta Cloud API webhook + Apps Script. Track B: Apps Script web app form | Zapier WhatsApp connectors are third-party paid. Zapier is unreliable on outbound. Apps Script is free inside Workspace. |
| Claude CoWork + skills + MCP | Same. In stack. | Claude Max 5x covers it. |
| Claude Dispatch | Claude mobile app | Secondary input path. Already paid for. |
| QuickBooks labor sync | Deferred. Simple LABOR tab in Sheets. | No accounting tool added without Amber. |
| ContractorOS community | Rejected. Build in-house. | Prior decision stands. No paid community. |

## 4. Hard constraints
- No new paid tools. No Airtable, Notion, SmartSheet, ContractorOS.
- Track A uses WhatsApp Cloud API only. Inbound free. Service-window replies free. Never send paid template messages.
- No unofficial WhatsApp APIs (Whapi, Green-API, whatsapp-web.js bots). Account ban risk and mostly paid. Rejected.
- Track B must not touch the Regina training portal files. The diary page is a separate page that sits beside it. Reserved Regina palette hexes (#1e3a8a, #1d4ed8, #93c5fd) are off limits for the diary UI.
- Test in sandbox copies before touching any live sheet or the live website. No exceptions.
- DELIVERIES data contains supplier names. Internal only. Never include in any export, report, or document that could leave the building.
- No em-dashes in any generated document or code comment. Short sentences. Specific numbers.

## 5. Track B design (website portal hub)
- Page: mobile-first diary entry form. Fields: project (dropdown), date (defaults today), free-text update box, weather, photo upload, optional voice note upload. One submit button.
- Voice path: supervisor records a voice memo on their phone and uploads it. File lands in Drive /Site Diary/Voice Notes. Cowork transcribes and processes it like any other raw message.
- Backend: Apps Script web app. doGet serves the form. doPost writes a row to RAW_MESSAGES (source: portal) and saves uploads to Drive.
- Login: restrict the web app to company Google accounts if field crew have them. If they do not, fall back to a per-supervisor access code checked server-side. Flag which applies (section 10).
- Website link: add a "Site Diary" link on the portal landing area next to the training portal entry. Cowork handles the page placement the same way the Regina portal was published.
- Group chat capture under Track B: WhatsApp groups can still be harvested by manual chat export to Drive /Site Diary/Chat Exports, parsed by Cowork. Optional, not required for go-live.

## 6. Architecture (downstream, identical for both tracks)
- All raw input lands in RAW_MESSAGES (api, portal, or export source).
- Processing: Cowork daily routine (skill: site-diary) reads unprocessed rows, extracts structured fields, drafts clarifying questions when data is missing, writes to DIARY, LABOR, QUANTITIES, DELIVERIES, DELAYS, TASKS. Marks rows processed.
- Approval: daily summary sent to the supervisor. Track A: Cloud API reply. Track B: email, or shown on the portal page at next login. Diary row flagged Approved only after confirmation.
- Output: dashboard tab plus a weekly digest to Owner. DELAYS tab is the claims backbone with dated weather and disruption records.

## 7. Google Sheets schema (one spreadsheet: "NC Site Diary")
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
Seed COST_CODES from the Your Company baseline: fab at 11 hr/ton, shop rate $145/hr. Start with fewer than 15 codes (fab, erection, deck install, detailing, mobilization, punch).

## 8. Build phases
- Phase 0. Decisions from Owner (section 10), including the Track A/B gate. No build until approved.
- Phase 1 (track-independent, start now): sandbox spreadsheet, site-diary skill, parse one real chat export end to end. Prove the loop with 1 pilot week of entries.
- Phase 2A (if Track A): Meta Business account, WhatsApp Business Platform app, number verification, deploy Apps Script webhook. Sandbox test with a test number first.
- Phase 2B (if Track B): build the Apps Script web app form in sandbox, test on a phone, confirm login method, then publish and link from the website.
- Phase 3. Approval loop, daily Cowork routine, weekly Owner digest.
- Phase 4 (later, optional): dashboard views and EVM rollups against COST_CODES.

## 9. Cowork vs Claude Code split
Cowork owns: Sheets schema, the site-diary skill, daily and weekly routines, export parsing orchestration, supervisor Q&A drafting, website page placement and link, this project's claude.md and project.md context files.
Claude Code owns the code. Cowork must write its own handoff file, CLAUDE_CODE_HANDOFF.md, covering whichever track is active:
1. Track A code: Apps Script doGet webhook verification (hub.challenge echo), doPost ingestion with dedupe on msg_id, append to RAW_MESSAGES, error logging tab.
2. Track B code: Apps Script web app. Mobile-first HTML form (no external JS), doPost handler, Drive upload for photos and voice notes, auth check (Google account or server-side access code), append to RAW_MESSAGES. Clasp-ready files.
3. Both tracks: WhatsApp .txt export parser handling multiline messages, "media omitted" markers, and 12h and 24h timestamp formats.
4. Test fixtures and locked tests: sample exports, sample payloads or form submissions, a two-step verification gate. Nothing writes to the live sheet or live site until the gate passes on sandbox copies.
The Claude Code handoff must include exact sandbox sheet IDs, the section 7 schema verbatim, acceptance tests, and the voice rules (no em-dashes anywhere).

## 10. Open items for Owner
1. Track gate: is a clean WhatsApp number available? No number means Track B.
2. Track B login method: do field crew have company Google accounts, or use per-supervisor access codes?
3. Pilot project selection.
4. Group chat export cadence and owner (optional under Track B).
5. Supervisor approval channel: WhatsApp reply, email, or portal.

## 11. Success criteria
- Supervisor diary entry takes under 3 minutes by voice or text on a phone.
- 100% of pilot inputs land in RAW_MESSAGES with zero duplicates.
- A diary row exists for every working day of the pilot week.
- Diary page (Track B) loads and submits on a phone over cell data in under 5 seconds.
- Zero paid tool spend. Zero template message charges. Regina portal untouched.

---
ANSWERS RECORDED 2026-06-10 (Owner via Cowork): 1. No number, Track B. 2. Register like the training page (Supabase signup code pattern). 3. Pilot: Genius Kids STEM Academy, Katy. 4. Open, optional. 5. Portal page.
