# Shop QC Software - Build Orchestration and Three-Agent Prompt Pack

**Document No.:** NC-IT-QC-SW-002
**Date:** June 18, 2026
**Prepared in:** Cowork (Your Company Virtual Office project)
**Supersedes the build instruction in:** NC-QC-SOFTWARE-HANDOFF.md (NC-IT-QC-SW-001) and the Joseph brief
**Status:** Review complete. Build instruction redirected. Prompt pack ready.

---

## 1. Bottom line up front

The Joseph brief tells Cowork to build the Shop QC application from scratch, starting at Section 15, Step 1 of the handoff. That build already exists in this project and is more complete and more correct than the handoff describes.

It lives at `ShopQC/` in the canonical mount. It is 2,064 lines of Python across the five-screen Tkinter app, the SQLite layer, BOL import, ZPL label printing, and seven ReportLab PDF outputs. Its headless logic test passes end to end:

```
SMOKE TEST PASS: gates, hard blocks, IDs, scan parse, labels, all 6 PDFs
```

So the correct action is not to rebuild. It is to verify, finish, and harden the existing app, then package and deploy it. This document does three things: it records the comparison, it lists the real remaining gaps, and it splits the remaining work into ordered prompts for Cowork, Claude Code, and Claude Design so the three tools build on each other instead of duplicating each other.

The end goal of the brief, a working digital execution of NC-QC-FAB-001 with three gates, 18-field travelers, QR labels, and hard-block enforcement, is preserved exactly. Nothing in the locked rules (Section 8 of the brief) is softened by this plan.

---

## 2. Brief versus existing app: where the existing app already wins

The existing `ShopQC/` app already implemented the handoff and then corrected it. These are documented in `ShopQC/README.md` and confirmed in the code.

| Brief instruction | Existing app | Verdict |
|---|---|---|
| Send ZPL to `\\.\USB001` raw | Win32 spooler RAW via pywin32, with shared-printer UNC and file fallback | App is correct. `\\.\USB001` is unreliable on Windows 11. |
| SQLite with WAL mode (Hard Rule 11 of main CLAUDE.md) | `journal_mode=DELETE` + `busy_timeout` + write-retry | App is correct. WAL corrupts on SMB shares and OneDrive. Note: the desktop bid app uses WAL locally; the shop DB is on a share, so DELETE is the right call here. |
| `projects` table without tonnage | `projects` has `tonnage` and `ias_required` | App is correct. The Gate 3 CEO co-sign rule is unenforceable without these. |
| QR encodes piece ID only (open question) | Full payload `{piece_id}|{project_no}|{heat_no}|{received_date}`, scanner parses full or bare | App is correct and matches the Owner's 2026-06-10 lock. |
| Network drive (open question) | Shared Windows folder, OneDrive for nightly backup copy only | Resolved and documented in DEPLOY_JOSEPH.md. |

Both "open questions" in Section 12 of the handoff and Section 6 of the Joseph brief are already answered and locked. They do not need to go back to Owner.

All six hard blocks from the brief are enforced and tested: pre-weld CWI block (field 8), locked traveler sequence, NCR hold freeze, Gate 3 completeness re-verify, CEO co-sign for 50T or IAS, and the EOR-reference requirement before closing an unauthorized-field-modification NCR.

**Conclusion: keep the existing app. Do not rebuild. The brief's Section 15 build sequence is treated as already executed.**

---

## 3. Real remaining gaps (the actual work)

These are the genuine open items. Each is assigned to the tool best suited to it in Section 5.

**G1. Three checklist strings are reconstructed, not confirmed (low risk, not a build blocker).** The Joseph brief and the handoff are both in hand and fully specify the build. They reference a separate document, NC-QC-FAB-001, the Shop Fabrication Quality Control Program, which is not in this project (the handoff cites it at the original Claude Chat path `/mnt/user-data/outputs/NC-QC-FAB-001.pdf`). That program is the only source for exactly three things: the Gate 1 MTR checklist (its Section 4.1), the physical receiving checklist (4.2), and the seven NCR category names (Section 9). The app reconstructed those from standard AISC 207-25 practice. Everything else the program governs (the 18 traveler fields, the hard blocks, the five screens, the schema) is spelled out in the brief and already matches the app. So this does not block the build; it only means those three lists should be confirmed word for word when the program is handy. C2 does that reconciliation if and when the program PDF is provided.

**G2. No SJI joist traveler variant (this is why the software exists).** The triggering incident, per the project record in `company-details.md`, was Elite Crossing (Lake Jackson, TX): the first SJI-certified joist project, 42 of 30KCS4 at 50 ft spans (26,580 lb), with an "active joist deflection issue under field modification per AISC." So the failure was a deflection problem on K-series joists tied to a field modification. The brief calls for an SJI Spec 100-2020 joist-specific traveler variant with camber, seat, and bridging fields (handoff Section 10 standards table). The current app has one generic 18-field structural traveler with a single optional camber field. The exact instrument meant to catch that failure does not exist yet, and the field-modification angle also ties directly to hard block 6 (an unauthorized-field-modification NCR cannot close without an EOR sealed reference). Adding a joist variant touches traveler structure, so it needs the Owner's explicit approval (the 18-field structural sequence stays locked; the joist set is additive).

**G3. PDFs do not carry the approved logo (Tier 1 brand rule).** The ReportLab outputs use a text-only "YOUR COMPANY" header. The Logo Rules require the approved masters from `brand/logos/` (`your company.png` black mark for light areas, `Your Company LLC.png` silver-on-dark for the dark header). The Final Release Certificate is a customer-facing trust artifact and must carry the real mark.

**G4. Thin test coverage and no ship gate.** There is one smoke test. The desktop bid app holds a 92/92 self-test line before ship. The QC app should have a real pytest suite and a green-before-ship gate, plus AISC 303-22 tolerance reference values shown next to the dimensional fields and structured ASTM Fy/Fu/CE capture at Gate 1.

**G5. Packaging and deployment not executed.** `build_exe.bat` exists but the signed EXE, the three-station rollout, the Zebra printer and scanner bring-up, and the test-loop validation are Windows-host tasks for Joseph. They cannot run in the Cowork sandbox.

**G6. UI is default Tkinter (cosmetic, low priority).** Functional and fine for a shop floor. Brand palette tokens and an app icon would align it, but this never blocks shipping.

---

## 4. Who does what, and why

The split follows the project routing rules: code to Claude Code, visual and print design to Claude Design, verification and content-accuracy and orchestration to Cowork.

- **Cowork** owns verification, the controlled-document wording reconciliation (the README itself notes these strings are "data, not logic"), deployment-doc polish, and keeping this plan and the follow-ups straight. No Windows toolchain needed.
- **Claude Code (Opus / Ultra, running on the real Windows repo)** owns the heavy engineering: the joist variant, logo embedding in ReportLab, the pytest suite and ship gate, tolerance and ASTM capture, code review against the six hard blocks, and the EXE build. It has the full toolchain and can run `build_exe.bat` and the tests.
- **Claude Design** owns the visual and print artifacts: the branded Final Release Certificate layout, the 2x1 inch QR label proof, the three gate-station SOP placards, the shop-floor workflow wall chart, and the brand palette and icon tokens that Code then applies.

---

## 5. Ordered build plan

Run in this order. Items marked "parallel" can run at the same time as the item above them.

```
STEP 1  COWORK   C1  Verify current state + publish this gap register        [done]
STEP 2  COWORK   C2  Finalize 3 checklists from standards (basis of record)  [done provisionally]
STEP 3  CODE     K1  Add SJI joist traveler variant                          (needs C2 + CEO ok)
STEP 3  DESIGN   D3  Brand palette tokens + app icon            (parallel with K1)
STEP 4  DESIGN   D1  Branded Final Release Certificate layout    (needs C2, coordinates with K1)
STEP 4  DESIGN   D2  QR label proof + gate placards + wall chart  (parallel with D1)
STEP 5  CODE     K2  Embed approved logo in all PDFs              (needs D1 + D3)
STEP 6  CODE     K3  pytest suite, ship gate, tolerance + ASTM capture
STEP 7  CODE     K4  Hard-block code review, then EXE build       (last; needs K1-K3)
STEP 8  JOSEPH   J1  Three-station deployment + hardware bring-up (Windows host)
```

Start state:
- **G1 / C2** is optional and non-blocking. The brief is in hand; only three checklist strings await word-for-word confirmation against the NC-QC-FAB-001 program if and when it is provided. K1 and D1 proceed now on the current wording, flagged.
- **G2 / K1** changes traveler structure, so it needed the Owner's explicit yes before Code starts. APPROVED by Owner 2026-06-18. K1 is cleared to build on a branch.

---

## 5a. Canonical test fixture and first project: Hillcrest 380 Building 1

The realistic input the QC app ingests is a real bid package, not the QC program. The one selected (the Owner's call: the most accurate recent bid in the files) is **Hillcrest 380 Building 1**, proposal **PRJ-2026-HILLCREST-STR-001**, sent by Owner on 2026-06-18 to Crossland (GC) with Joseph, Ivan, and Amber CC'd. It is saved into the repo at `ShopQC/data/test_fixtures/` as the extracted text plus a text-layer PDF for the parser; the original 111 KB PDF of record stays in Joseph's Outlook.

Why this one: it is the most complete current package (176,800 SF, $1,752,364) and it is the only fixture that carries the full joist scope the app must prove: SJI open-web joists (30K and 20K series), moment joist girders (60G and 72G series), bridging per SJI, plus A992 W-shapes, A500 HSS columns, 22 GA Type B deck, and F1554 Gr 36/55 anchors. That joist content is exactly what K1 (the joist variant) needs to exercise, and it matches the Elite Crossing failure mode.

One honest limit: this is a scope-and-tonnage proposal, not a per-piece member schedule. It tests project setup, the joist/deck/anchor scope, and the parser's section detection. Per-piece marks and heat numbers are assigned at receiving from the shipper BOL and MTRs, which is the real Gate 1 flow, so manual or section-level entry there is expected. This fixture does NOT replace the NC-QC-FAB-001 program PDF (G1); that is the QC program text and is still needed for C2.

## 6. The prompts

Copy each block into the named tool, in order. Each is self-contained.

---

### PROMPT C2 - COWORK - Finalize checklists from standards (DONE provisionally), reconcile later

```
Default path (program NOT provided) - ALREADY DONE 2026-06-18:
Per CEO direction, the three reconstructed lists (MTR 4.1, physical 4.2, NCR
categories Sec 9) were finalized from the governing standards and adopted as the
working standard. The basis of record, with a standard cited for every line, is
ShopQC/QC-FAB-001-RECONCILIATION-2026-06-18.md (status PROVISIONAL). The 18
traveler fields were confirmed to match the brief verbatim. No code change was
needed; the existing constants are standards-sound. The build proceeds on these.
Nothing waits on the program PDF.

Reconcile path (run ONLY if NC-QC-FAB-001 is later provided):
1. Read NC-QC-FAB-001 Sections 4.1, 4.2, 8, and 9.
2. Compare to the constants: MTR_CHECKS and PHYS_CHECKS in
   ShopQC/shopqc/ui/receiving.py; NCR_CATEGORIES and TRAVELER_FIELDS in
   ShopQC/shopqc/db.py.
3. For the three data-only checklist/category constants, update strings in place to
   match the program exactly (labels, not logic). Keep the smoke test green.
4. For the 18 fields: the SEQUENCE is locked. Change only display labels, never the
   order or field kind. If the program shows more than 18 fields or a different
   field-8 hard-block point, STOP and flag for Owner.
5. Flip QC-FAB-001-RECONCILIATION-2026-06-18.md from PROVISIONAL to CONFIRMED with
   the date and the verbatim table.

Hard rules: no em-dashes. No supplier names. Surface uncertainty. Back up
receiving.py and db.py to _handoff/backups/<UTC-timestamp>/ before any edit and
append a line to _handoff/changelog.md.
```

---

### PROMPT K1 - CLAUDE CODE - SJI joist traveler variant   [APPROVED by Owner 2026-06-18]

```
Repo: the Your Company Virtual Office project, app at ShopQC/. Python 3.x, Tkinter,
SQLite, ReportLab. Read ShopQC/README.md and ShopQC/shopqc/db.py first.

Goal: add an SJI Spec 100-2020 joist-specific traveler variant. The triggering
incident (project record in company-details.md): Elite Crossing, Lake Jackson TX,
the firm's first SJI-certified joist project, 42 of 30KCS4 at 50 ft spans, with an
active joist DEFLECTION issue under a FIELD MODIFICATION per AISC. The current app
only has the generic structural traveler. This variant is the instrument that
should have caught that failure, so it must capture camber/deflection against the
SJI-specified value and must make a field modification traceable into the
unauthorized-field-modification NCR path (hard block 6: no close without an EOR
sealed reference).

Constraints (do not violate):
- The existing generic 18-field structural traveler sequence in TRAVELER_FIELDS is
  a locked controlled value. Do NOT reorder or delete it. The joist variant is
  ADDITIVE and selected per piece, not a replacement.
- All six hard blocks must hold for the joist variant too: pre-weld CWI block,
  locked sequence (only the lowest unsigned floor step signable), NCR hold freeze,
  Gate 3 completeness re-verify, CEO co-sign at >= 50T or IAS, EOR reference before
  closing an unauthorized-field-modification NCR.
- Weights and section data are never computed by the app. Source of truth stays
  bridge/aisc_validator.py in the Virtual Office. Joist designations (e.g. 30KCS4,
  K-series, LH, DLH) are validated by format, not invented.

Build:
1. Add a piece/traveler type ("STRUCTURAL" default, "JOIST") chosen at receiving
   from the BOL line or section pattern (K, KCS, LH, DLH, SLH series detected).
2. Define the joist field set per SJI Spec 100-2020 as a parallel locked sequence:
   joist mark, span/depth, chord and web checks, SEAT depth and type, BRIDGING rows
   installed and type, end-anchorage, CAMBER measured vs SJI-specified, paint/coating,
   plus the same CWI hold and Gate 3 release fields. Confirm the exact field list
   against NC-QC-FAB-001 and SJI Spec 100-2020 before finalizing; if the program
   does not enumerate joist fields, propose the set and flag it for Owner.
3. Store the variant on the piece so Gate 2 and Gate 3 load the right field set and
   the traveler PDF prints the right one.
4. Update tests/smoke_test.py (or add tests) to exercise a joist piece through all
   three gates including the camber and bridging checks and the CWI hard block. Use
   the Hillcrest 380 fixture (ShopQC/data/test_fixtures/PRJ-2026-HILLCREST-STR-001)
   as the realistic case: 30K and 20K open-web joists, 60G and 72G joist girders,
   bridging per SJI. Seed a joist piece from it and run it through Gate 2 and Gate 3.
5. Keep DB migration safe and additive (no destructive ALTERs on the shared file).

Deliver a short MIGRATION note describing schema changes and how existing pieces
keep working. No em-dashes. Do not change the structural sequence. This change
requires the Owner's sign-off before merge; build it on a branch and report back.
```

---

### PROMPT K2 - CLAUDE CODE - Embed approved logo in all PDFs

```
Repo: ShopQC/ in the Your Company Virtual Office project. Read ShopQC/shopqc/reports.py
and brand/LOGO_RULES.md first.

Goal: put the approved Your Company logo on every PDF the app produces (RIR,
traveler, weld log, NCR form, Final Release Certificate, shipping manifest, project
summary), per the Tier 1 logo rules.

Rules (Tier 1, do not deviate):
- Use only the approved masters: brand/logos/your company.png (black mark, for
  light backgrounds) and brand/logos/Your Company LLC.png (silver-on-dark, for the
  dark header band). Never recreate, stretch, skew, recolor, or outline the mark.
- The only permitted change is the background behind the mark. Silver-on-dark lockup
  goes in the existing dark (#141414) header band; if a mark sits on the white body,
  use the black mark.
- Bundle the logo files with PyInstaller (add to build_exe.bat --add-data) and load
  them via the existing resource_path() pattern so they resolve in the frozen EXE.

Implement the placement from Claude Design's spec (NC-QC Certificate layout). Keep
the red (#C8102E) accent rule under the header. Re-run tests/smoke_test.py; all PDFs
must still build and exceed the size assertion. No em-dashes in any output. No
supplier names ever appear in these PDFs.
```

---

### PROMPT K3 - CLAUDE CODE - Test suite, ship gate, tolerance and ASTM capture

```
Repo: ShopQC/. Read tests/smoke_test.py and shopqc/ui/receiving.py and
shopqc/ui/fabrication.py first.

Goal: raise this from "one smoke test" to "green-before-ship", matching the bid
app's discipline.

Build:
1. A pytest suite under ShopQC/tests/ covering: BOL parse of the Hillcrest 380
   fixture (ShopQC/data/test_fixtures/PRJ-2026-HILLCREST-STR-001.pdf) including its
   joist and deck scope, piece ID sequencing per project+section, full QR payload +
   bare-ID scan parse, the locked sequence,
   the pre-weld CWI hard block, NCR hold freeze and release, Gate 3 completeness
   re-verify, CEO co-sign at >= 50T and IAS, EOR-reference-before-close on the
   unauthorized-field-modification category, BOL parser confidence tagging, ZPL
   build, and all seven PDFs building. Keep the existing headless (no-Tkinter)
   style.
2. A one-line ship gate (e.g. tests/run_all.py or a pytest marker) that prints a
   PASS/COUNT line and exits non-zero on any failure, so Joseph can gate the EXE
   build on it.
3. At Gate 1, capture ASTM Fy / Fu / CE as structured fields (not just a checkbox)
   so the MTR record holds the actual values, per ASTM A992/A500/A36/F1554.
4. Next to the Gate 2 dimensional field (field 12) and the receiving straightness
   check, surface the AISC 303-22 tolerance reference value as on-screen helper
   text so the inspector sees the limit while entering the measurement.

Do not change the six hard blocks' behavior; test them, do not weaken them. No
em-dashes. Report the final test count.
```

---

### PROMPT K4 - CLAUDE CODE - Hard-block code review, then EXE build

```
Repo: ShopQC/. This is the pre-ship gate. Run after K1, K2, K3 are merged.

1. Code review against the six hard blocks in README.md. For each, point to the
   exact lines that enforce it and confirm it cannot be bypassed through the UI,
   the scan path, or a direct DB state. Pay special attention to: can any path mark
   field 8 signed without a CWI name; can the lowest-unsigned-step rule be skipped;
   can a piece release with an open NCR or an unsigned field after a late edit;
   does the CEO co-sign trigger correctly at exactly 50T and for IAS; can an
   unauthorized-field-modification NCR close without an EOR reference.
2. Multi-station concurrency review: confirm journal_mode=DELETE, busy_timeout, and
   execute_write retry behave under two stations writing the same piece. No WAL.
3. Run the full pytest suite and the ship gate. Must be green.
4. Run build_exe.bat. Confirm dist\ShopQC.exe builds, the bundled data (AISC CSV,
   logo PNGs) resolves at runtime, and config.json is created on first run.
5. Write a short SHIP-READINESS note: what passed, any residual risk, and the exact
   command Joseph runs.

No code changes that alter behavior during this pass unless you find a hard-block
defect; if you do, fix it, add a regression test, and call it out. No em-dashes.
```

---

### PROMPT D1 - CLAUDE DESIGN - Branded Final Release Certificate layout

```
Design a print layout for the Your Company Final Release Certificate, US Letter
portrait. This is the customer-facing proof that a fabricated steel piece cleared
all three QC gates of NC-QC-FAB-001. It is generated in ReportLab, so deliver a
layout spec and a visual mockup that a developer can reproduce: margins, grid,
type sizes, exact element positions, and color hex values.

Brand (Tier 1, fixed):
- Logo: use only the approved masters. Silver-on-dark lockup (brand/logos/Your Company
  USA LLC.png) on a dark header band; black mark (brand/logos/your company.png) if
  any mark sits on white. Never alter the mark.
- Colors: dark #141414, red accent #C8102E, Helvetica family, white body.
- No em-dashes. No supplier names anywhere. Do not list precedent projects.

Content to lay out (data comes from the app): company header with logo, certificate
title, piece ID, section, heat number, project name and job number, the statement
that all 18 (or joist-variant) traveler fields are signed and zero NCRs are open,
and a signature block for Shop Director, CWI, and an optional CEO co-sign line
(shown only for projects >= 50 tons or IAS). Coordinate the field-completeness
wording with Claude Code's joist variant (K1) so it reads correctly for both
structural and joist pieces.

Deliver: the mockup plus a positions-and-tokens spec handed to Claude Code (K2).
```

---

### PROMPT D2 - CLAUDE DESIGN - Label proof, gate placards, workflow wall chart

```
Three shop-floor print artifacts for Your Company. Brand: dark #141414, red accent
#C8102E, Helvetica, approved logo masters only, no em-dashes, no supplier names.

1. QR LABEL PROOF: a 2 x 1 inch thermal label at 203 dpi (406 x 203 dots). Show the
   QR block on the left and human-readable lines on the right: piece ID, section,
   project name (truncated), date, and a small 