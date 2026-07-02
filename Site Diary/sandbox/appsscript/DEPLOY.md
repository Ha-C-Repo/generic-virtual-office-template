# Site Diary Apps Script - Sandbox Deploy Guide

One-time Google-side setup. Everything below runs against SANDBOX
resources only. The live "NC Site Diary" sheet does not exist yet and
must not be created until the Step 1 verification gate passes and
Owner signs off Step 2.

Account: the same Google account that owns the Workspace Drive
(yourcompanyjoseph@gmail.com per the training portal deploy notes).

## Files in this folder

- `Code.gs` - web app: doPost entry ingestion, doGet pending feed,
  approve action, hardened (25 MB cap, MIME allowlist, LockService).
- `Setup.gs` - setupSandbox() provisioning, selfCheck() verifier.
- `appsscript.json` - V8, web app runs as the deploying user, access
  anyone anonymous. Page-level auth is Supabase; request-level auth is
  the shared secret.

## Path A: copy-paste (recommended, no installs)

1. Go to script.google.com. New project. Name it "NC Site Diary SANDBOX".
2. Replace the default Code.gs content with this folder's `Code.gs`.
   Add a second script file named `Setup` and paste `Setup.gs`.
3. Project Settings > check "Show appsscript.json manifest file".
   Replace its content with this folder's `appsscript.json`.
4. In the editor, select function `setupSandbox` and Run. Approve the
   permission prompts (Sheets plus Drive, this account only).
5. Open Execution log. Copy the four logged values:
   - SHEET_ID: paste into `Site Diary/CLAUDE_CODE_HANDOFF.md` at the
     `SANDBOX_SHEET_ID =` line.
   - SHARED_SECRET: goes into `diary.js` at deploy (step 7).
6. Run `selfCheck`. The log must end with SELF CHECK PASSED.
7. Deploy > New deployment > Web app.
   - Execute as: Me.
   - Who has access: Anyone.
   - Copy the /exec URL.
8. Wire the front end: in the portal repo `diary.js`, set EXEC_URL to
   the /exec URL and SECRET to the shared secret. These two values are
   set at deploy time only. Do not commit real values until Owner
   clears the go-live, and never to any public repo.

## Path B: clasp (repeatable pushes)

```
npm install -g @google/clasp
clasp login
cd "Site Diary/sandbox/appsscript"
clasp create --type webapp --title "NC Site Diary SANDBOX"
clasp push
```

Then steps 4 to 8 from Path A (run setupSandbox in the editor once,
deploy, wire diary.js). `clasp push` is the update path for later
Code.gs revisions; redeploy or use a versioned deployment after a push.

## Smoke tests (sandbox, before the phone test)

Health check. Expect `{"ok":true,"service":"nc-site-diary",...}`:

```
curl -L "<EXEC_URL>?secret=<SECRET>"
```

Wrong secret. Expect `{"ok":false,"error":"denied"}` and zero new rows:

```
curl -L "<EXEC_URL>?secret=wrong"
```

Entry post. Expect `{"ok":true,"msg_id":"portal-..."}` and exactly 1
new RAW_MESSAGES row. Repeat the same command: expect `"dedupe":true`
and zero new rows:

```
curl -L -X POST -H "Content-Type: text/plain" -d "{\"secret\":\"<SECRET>\",\"sender\":\"test@yourcompany.example.com\",\"project\":\"Genius Kids STEM Academy (Katy)\",\"date\":\"2026-06-10\",\"weather\":\"Clear\",\"body\":\"smoke test entry\"}" "<EXEC_URL>"
```

## Local logic tests (already runnable, no Google account)

`test/run_tests.js` in this folder exercises Code.gs against mocked
Sheets, Drive, and Lock services:

```
node test/run_tests.js
```

All tests must pass before deploying a Code.gs change, same idea as
the parser's 16 locked tests.

## Hardening notes

- Per-file upload cap 25 MB decoded. Request cap 12 files. Whole-entry
  cap 30 MB decoded, because Apps Script rejects POST bodies around
  50 MB at the platform layer before doPost runs. The page mirrors all
  three caps so the phone fails fast instead of after a long upload.
- MIME allowlist: photos must be image types, voice notes audio types.
  Anything else is rejected before any write.
- LockService wraps the dedupe check plus appendRow. Two concurrent
  identical submits write exactly 1 row.
- Dedupe key: sha1 of sender|date|body|weather|uploads metadata, first
  16 hex, portal- prefix. A pure retry of the same form state dedupes
  to zero rows. Resubmitting the same text with new photos or changed
  weather is a new entry, so late attachments are never dropped.
- Approve checks the row's supervisor column against the caller before
  setting approved and approved_ts.
- Wrong secret short-circuits before any read or write.
- Errors append to the ERRORS tab (timestamp, error).

Phase 2 hardening candidate, not in sandbox scope: verify the Supabase
access token server-side in Apps Script via the Supabase auth endpoint
so the sender field is provable, not page-asserted.
