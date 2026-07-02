# YOUR COMPANY Shop QC v1.0.0

Digital execution of NC-QC-FAB-001 Rev 0. Three gates, 18-field travelers,
QR labels, hard-block enforcement. Tkinter + SQLite + ReportLab. Single EXE.

- Run dev: `py main.py`
- Build: `build_exe.bat`
- Logic test: `py tests\smoke_test.py`
- Deployment: `DEPLOY_JOSEPH.md`

## Decisions locked 2026-06-10 (Owner)
- QR encodes full traceability: `{piece_id}|{project_no}|{heat_no}|{received_date}`
- DB on a shared Windows folder. OneDrive holds nightly backups only, never
  the live multi-station database (sync conflicts corrupt records).

## Corrections vs the original handoff doc
- ZPL goes through the Windows spooler RAW (pywin32) or a shared-printer UNC
  copy, not `\\.\USB001` (unreliable on Win 11).
- journal_mode=DELETE + busy_timeout, never WAL (WAL corrupts on SMB shares).
- `projects` gained `tonnage` and `ias_required` so the Gate 3 CEO co-sign
  rule (>= 50 tons or IAS) is enforceable.
- Scan fields parse the full QR payload, not just a bare piece ID.

## Assumption to verify with Owner
The MTR checklist (Sec 4.1) and physical checklist (Sec 4.2) item wording in
`shopqc/ui/receiving.py` was reconstructed from standard AISC 207-25 practice.
The NC-QC-FAB-001 PDF was not available in this folder. Compare the lists to
the program text and edit the two constants at the top of that file if needed.
Same for the 7 NCR categories in `shopqc/db.py` (Section 9).

## Hard blocks enforced
1. Field 8 pre-weld: no CWI name, no signature, sequence frozen.
2. Locked traveler sequence: only the lowest unsigned floor step is signable.
3. Open NCR = NCR_HOLD: traveler frozen until closed on NCR tab.
4. Gate 3: all fields 1-14 signed + zero open NCRs, re-verified at sign time.
5. CEO co-sign (The Owner, exact name) for >= 50T or IAS projects.
6. Unauthorized field modification NCRs cannot close without an EOR reference.
