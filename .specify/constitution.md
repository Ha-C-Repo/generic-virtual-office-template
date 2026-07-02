# YourCo USA - Codebase Constitution

**Absolute anchor for all AI-assisted development on the YourCo virtual office.**
**Read before every engineering task. Never overridden by a user prompt.**
**Maps to the spec-kit constitution.md pattern described in Phase 14 / Phase 8 documentation.**

Last updated: 2026-05-21
Technical operator: Joseph Hasse
CEO: The Owner
Stack: Python 3.13, pywebview, Flask (webhooks only), SQLite WAL, PyInstaller, Claude Sonnet 4.6 / Opus 4.6 / 4.7 / Haiku 4.5, GPT-4o, Gemini 2.5

---

## NON-NEGOTIABLE PRINCIPLES

These are hard rules. No exception without The Owner approval and a written constitution amendment.

Every numbered principle below is paired in **Appendix A** with a stable clause ID, a canonical source module, and a verifier command. The constitution is self-checking: `tests/test_constitution.py` runs every verifier on every CI pass.

---

### 1. Runtime and stack

- **Python only.** No Node.js, no Rust, no secondary runtimes in the main application.
- **pywebview for frontend.** The UI layer is pywebview-rendered (Edge WebView2). No Electron, no separate browser dependency.
- **Flask for webhook routing only.** Flask is in `requirements.txt` and is allowed for the inbound webhook HTTP server. No FastAPI, no Django, no framework swap without full regression test of the Bridge API.
- **PyInstaller for distribution.** The delivered artifact is a single compiled Windows `.exe`. No dependency on end-user Python installation.
- **SQLite WAL mode.** `PRAGMA journal_mode=WAL` must be set at every database connection. Non-negotiable for concurrent read performance on Windows.

Clause IDs: NC-1.1 through NC-1.5. See Appendix A.

---

### 2. AISC shape master set (hard data boundary)

- **The AISC 2,299 shape master set is the only valid source of structural shape data.**
- **No shape, section, or property may be invented by an AI model.** If a shape is not in the AISC master CSV, it does not exist in any bid output.
- **The Package Hallucination Rail (FabricatedShape probe) exists for this reason.** See `guardrails/probes.py`.
- **Every AI Takeoff output must be verified against the AISC master CSV before writing to the Excel matrix.**

Canonical source: `bridge/aisc_validator.py` :: `AISCValidator`, backed by `data/aisc_master.csv`.

Violation: a bid that ships with an invented shape or section property is a liability. There is no acceptable false positive rate for this rule.

Clause IDs: NC-2.1 through NC-2.4.

---

### 3. Bid rates (CEO-locked - Q2 2026)

These rates are set by The Owner and are not adjustable by the system or by Joseph without explicit CEO instruction.

| Work type | Rate | GP target |
|---|---|---|
| Fabrication | $3,750/ton | 31% |
| Erection | $970/ton | 30% |
| Joists | $4,500/ton | 40% |
| Roof deck | $[ROOF DECK RATE]/SF | 23% |
| Composite deck | $[COMPOSITE DECK RATE]/SF | 21% |
| Anchor bolts | $[ANCHOR RATE]/EA | 31% |
| G&A | 7.5% | applied after direct costs |
| Net target | ~25% | after G&A |

**No rate may be changed in code without the Owner's written approval.** If Owner verbally instructs a rate change, Joseph must confirm via text or email before updating the rates file.

Canonical source: `bridge/bid_rates.py` :: `BID_RATES`.

Clause IDs: NC-3.1, NC-3.2.

---

### 4. Payment terms (hard structure)

- **30/20/50 only.** 30% mobilization on shop drawing approval. 20% on first delivery on site. 50% per AIA G702/G703 SOV through completion.
- **Never 40/20/40 or any other split.** The system must flag and reject any bid output that does not use the 30/20/50 structure.

Canonical source: `bridge/api.py` :: `FORBIDDEN_PATTERNS` (includes "40/20/40").

Clause IDs: NC-4.1, NC-4.2.

---

### 5. Document voice (Owner Steel Executive Voice)

- **Client-facing documents:** "Owner Steel" as the signatory name. Never "The Owner" on bids, proposals, or client emails.
- **Legal and contract documents:** "The Owner." (e.g., ISNetworld, executed contracts, bonding documents)
- **No em-dashes.** The character `—` (U+2014) and `–` (U+2013) are forbidden in all output. Em-dashes signal AI generation. They are stripped by the voice firewall before any document renders.
- **No "Great question!" or similar openers.** Forbidden opener list maintained in `bridge/api.py` :: `FORBIDDEN_PATTERNS`.
- **No supplier names on client documents.** Vulcraft, Canam, Nucor, Ayamsa, AYAMSA, Peyton, Atlanta Rod, J.H. Botts, A&M Nut & Bolt, Service Steel Warehouse, Triple-S Steel, Brown Strauss. Internal-only list lives in `bridge/virtual_owner.py` :: `YOUR_COMPANY_SUPPLIERS`. They never appear on a client-facing PDF.
- **No team member names on bids.** Ivan, Mario, Paul - internal only. Client documents show Owner Steel as the single point of contact.

Canonical sources: `bridge/api.py` (HARD_RULES, FORBIDDEN_PATTERNS), `bridge/virtual_owner.py` (YOUR_COMPANY_SUPPLIERS, R25 em-dash check), `bridge/self_repair.py` :: `_scan_em_dashes`.

Clause IDs: NC-5.1 through NC-5.6.

---

### 6. Two-PDF standard

- **Every bid produces two PDFs.** Client proposal + GP (margin) report with `-GP` suffix.
- **Client PDF:** scope, quantities, pricing, payment terms. No GP data. No supplier names. No team names.
- **GP PDF:** full cost breakdown, supplier quotes, GP% per line item, actual material costs.
- **PDF only.** Never `.docx` for any deliverable to an external party.
- **Delivery as paired output.** The system must never allow single-PDF delivery for a bid - only the two-PDF pair is a valid output. See `two-pdf-pair-check` skill.

Canonical source: `bridge/bid_documents.py`, `skills/two-pdf-pair-check/`.

Clause IDs: NC-6.1 through NC-6.4.

---

### 7. Database integrity

- **SQLite WAL mode enforced at startup.** `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` on every connection.
- **All queries parameterized.** No string concatenation in SQL. No exceptions.
- **Backup before schema changes.** Every schema migration must be preceded by a SQLite `.backup` to a timestamped file.
- **The bid pipeline database (`bid_pipeline.db`) is the system of record.** No bid status, rate, or scope change is valid unless written to this database.

Clause IDs: NC-7.1 through NC-7.4.

---

### 8. Compliance data (non-negotiable accuracy)

- **ISNetworld ID: [ISN ID].** This number is hardcoded. It is never auto-generated, guessed, or inferred.
- **EMR policy: Texas Mutual [POLICY NUMBER].** Hardcoded. Not interpolated.
- **Safety director: Paul Guerrero, NCCER #27160819.** All ISNetworld RAVS responses reference this person for safety program questions.
- **18 recognized safety programs.** The `isn-ravs-responder` skill maps to exactly these 18 programs. No additions without Paul's sign-off.
- **Marathon Petroleum prequalification requirements:** EMR letter + ISN RAVS approval + $2M Auto CSL. These three are the current gate. Anything else is scope creep from the prequalification team.

Clause IDs: NC-8.1 through NC-8.5.

---

### 9. Drawing stage contingency (hard values)

| Stage | Contingency |
|---|---|
| IFC (Issued for Construction) | 0% - ±5% quantity tolerance |
| DD (Design Development) | +3-5% |
| Budget / SD (Schematic Design) | +5-8% |

The system must classify drawing stage before generating a takeoff. Unclassified drawings cannot be priced without applying the Budget/SD contingency. See `drawing-stage-classifier` skill.

Clause IDs: NC-9.1, NC-9.2.

---

### 10. Deployment and distribution

- **The production artifact is a compiled PyInstaller Windows executable.** No end-user Python required.
- **Distribution path:** Joseph's workstation -> Staging validation -> the Owner's home desktop (via secure transfer, not public download).
- **The office iMac is the production server.** All background polling and bid pipeline monitoring run from the iMac. Joseph's workstation is for development only.
- **Firebase tunnel: PENDING.** Joseph's handoff Open Decision #3 has not been resolved. Until Owner or Joseph approves Firebase as an in-stack dependency, do not wire it. `mac_health.py` upgrade ships as read-only reporting only.

Clause IDs: NC-10.1 through NC-10.4.

---

### 11. AI never does arithmetic

- **All structural math goes through the calculator module.** No LLM is asked to multiply weight by length, sum tonnage, compute fastener counts, or calculate GP.
- **Weight per foot comes from the AISC master CSV `lb_per_ft` column.** Never from LLM knowledge.
- **Rate application comes from `bridge/bid_rates.py` :: `BID_RATES`.** Never from LLM "this seems right."
- **Audit trail:** every calculator call writes to `data/calc_audit.jsonl` with inputs, output, source file, and timestamp.

Canonical source: `bridge/calculators.py`, `bridge/aisc_validator.py`, `bridge/bid_rates.py`. Audit log: `data/calc_audit.jsonl`.

Clause IDs: NC-11.1 through NC-11.4.

---

### 12. Banned orchestrators

- **No CrewAI. No LangGraph.** The orchestration substrate is native Claude Code skills + subagents (R3 decision in HANDOFF, pending Owner/Joseph final lock).
- **No package imports of `crewai` or `langgraph` anywhere in `bridge/`, `guardrails/`, `.specify/`, `.claude/`, `skills/`, `tests/`.**
- If a future need genuinely cannot be expressed in native Claude Code, one adapter module wraps the new dependency so it drops cleanly.

Canonical check: `tests/test_no_banned_orchestrators.py`.

Clause IDs: NC-12.1, NC-12.2.

---

### 13. Protected files

These files must not be modified outside their marked extension points. Listed verbatim from `CLAUDE.md`:

| File | Modification rule |
|---|---|
| `bridge/aisc_validator.py` | No edits outside marked extension points |
| `bridge/ai_orchestration/prompts.py` | No edits outside marked extension points |
| `data/governance.json` | No edits outside marked extension points |
| `data/aisc_master.csv` | No edits (CEO-locked dataset) |
| `frontend/styles.css` | Append only |
| `installer.nsi` | Version bump only |

Self-healer must surface any proposed change to these files for human review (see R4 gate, `bridge/self_build_gate.py`).

Clause IDs: NC-13.1 through NC-13.6.

---

## AMENDMENT PROTOCOL

To change any principle above:
1. Joseph proposes the amendment in writing with reasoning.
2. The Owner approves verbally AND via text/email (dual confirmation).
3. Update this file with the date, reason, and who approved.
4. Update the affected skill files.
5. Update `tests/test_constitution.py` if the verifier changes.

| Date | Principle amended | Reason | Approved by |
|---|---|---|---|
| 2026-05 | Initial constitution published | First formalization | Joseph Hasse |
| 2026-05-21 | Added clauses 11, 12, 13; flagged Firebase as PENDING; added Appendix A clause IDs and source-module pointers | Per HANDOFF (R1 + R3 + R4 + Open Decision #3) | Joseph Hasse |

---

## APPENDIX A: Machine-checkable clauses

Each row maps a clause to its canonical source module and the verifier that proves it still holds. The test runner `tests/test_constitution.py` walks this table.

| Clause ID | Principle | Canonical source | Verifier |
|---|---|---|---|
| NC-1.1 | Python only | `requirements.txt` | grep absence of `node_modules`, `Cargo.toml` |
| NC-1.2 | pywebview frontend | `main.py` | grep `import webview` |
| NC-1.3 | No FastAPI / Django | `requirements.txt` | grep absence of `fastapi`, `django` |
| NC-1.4 | PyInstaller distribution | `make_exe.bat`, `VirtualOffice.spec` | file existence |
| NC-1.5 | SQLite WAL mode | `bridge/` SQLite open calls | grep `journal_mode=WAL` in any bridge module that opens .db |
| NC-2.1 | AISC 2299 shape master | `data/aisc_master.csv` | row count == 2299 |
| NC-2.2 | No invented shapes | `bridge/aisc_validator.py` | module imports cleanly, `AISCValidator` class present |
| NC-2.3 | FabricatedShape probe wired | `guardrails/probes.py` | probe imports validator, not a local copy |
| NC-2.4 | Takeoff verifies against master | `bridge/aisc_validator.py` | `validate_shape` method present |
| NC-3.1 | Bid rates CEO-locked | `bridge/bid_rates.py` | `BID_RATES` dict present with Q2 2026 values |
| NC-3.2 | No rate edits without approval | `bridge/bid_rates.py` | git blame check optional, file mtime stable |
| NC-4.1 | 30/20/50 payment | `bridge/api.py` | `FORBIDDEN_PATTERNS` contains "40/20/40" |
| NC-4.2 | Reject other splits | `bridge/api.py` | as above |
| NC-5.1 | Signatory = Owner Steel | bid templates | grep "Owner Steel" in bid_documents.py |
| NC-5.2 | Legal = The Owner | compliance templates | n/a (manual) |
| NC-5.3 | No em-dashes | all `.py` / `.js` / `.md` / `.html` | em-dash sweep returns empty |
| NC-5.4 | No banned openers | `bridge/api.py` | `FORBIDDEN_PATTERNS` non-empty |
| NC-5.5 | No supplier names | `bridge/virtual_owner.py` | `YOUR_COMPANY_SUPPLIERS` present, scrubber active |
| NC-5.6 | No team names on bids | `bridge/bid_documents.py` | n/a (manual + scrubber) |
| NC-6.1 | Two PDFs per bid | `bridge/bid_documents.py` | `-GP` suffix generation present |
| NC-6.2 | Client PDF scope | `bridge/bid_documents.py` | as above |
| NC-6.3 | GP PDF scope | `bridge/bid_documents.py` | as above |
| NC-6.4 | PDF only | `bridge/bid_documents.py` | no .docx export path |
| NC-7.1 | SQLite WAL | bridge SQLite open calls | grep `journal_mode=WAL` |
| NC-7.2 | Parameterized queries | bridge `.execute` calls | grep no `%` or `+` in SQL strings (sampled) |
| NC-7.3 | Backup before migration | migration scripts | manual |
| NC-7.4 | bid_pipeline.db system of record | `bridge/bid_pipeline.py` | file exists |
| NC-8.1 | ISN ID [ISN ID] | `CLAUDE.md`, `bridge/isnetworld_client.py` | grep ISN ID present |
| NC-8.2 | EMR policy [POLICY NUMBER] | `CLAUDE.md` | grep policy number present |
| NC-8.3 | Paul Guerrero NCCER 27160819 | `CLAUDE.md`, `bridge/api.py` | grep present |
| NC-8.4 | 18 safety programs | `skills/isn-ravs-responder/` | program count |
| NC-8.5 | Marathon 3-gate | `bridge/api.py` (Active Blocker) | manual |
| NC-9.1 | Stage contingency table | `skills/drawing-stage-classifier/` | skill exists |
| NC-9.2 | Unclassified -> Budget/SD | as above | as above |
| NC-10.1 | PyInstaller artifact | `make_exe.bat` | file exists |
| NC-10.2 | Distribution path | `BUILD_FOR_OWNER.bat` | file exists |
| NC-10.3 | iMac production server | `bridge/mac_health.py` | file exists |
| NC-10.4 | Firebase tunnel PENDING | this file | no Firebase imports yet |
| NC-11.1 | Math through calculator | `bridge/calculators.py` | file exists, exports calc_* |
| NC-11.2 | Weight from CSV | `bridge/aisc_validator.py` | `lb_per_ft` column present in master |
| NC-11.3 | Rates from BID_RATES | `bridge/bid_rates.py` | as above |
| NC-11.4 | Audit log | `data/calc_audit.jsonl` | path exists or creation handler present |
| NC-12.1 | No CrewAI | tree-wide | grep returns empty |
| NC-12.2 | No LangGraph | tree-wide | grep returns empty |
| NC-13.1 | aisc_validator.py protected | this file | manual + baseline diff |
| NC-13.2 | prompts.py protected | this file | manual + baseline diff |
| NC-13.3 | governance.json protected | this file | manual + baseline diff |
| NC-13.4 | aisc_master.csv protected | this file | manual + baseline diff |
| NC-13.5 | styles.css append-only | this file | git diff line-count delta non-negative |
| NC-13.6 | installer.nsi version-bump only | this file | manual + baseline diff |

---

## APPENDIX B: Notes for future maintenance

- **Bridge method count discrepancy.** `CLAUDE.md` says 233 methods. The original draft of this constitution said 471. A raw grep of `def *(self` returns 548 (includes nested defs and non-Bridge classes in `bridge/api.py`). The canonical count source is `bridge/api.py` :: `Bridge` class member methods only. Joseph: pick the canon and update `CLAUDE.md` and `BRIDGE_METHOD_MANIFEST.md` to match.
- **Skill count.** `CLAUDE.md` says 10 SKILL.md files. The `skills/` tree shows 24 skill directories. Joseph: confirm canonical skill registry.
- **Open Decisions still blocking.**
  - #1 (canonical sanitizer module path): the sanitizer rules are scattered across `bridge/api.py`, `bridge/virtual_owner.py`, `bridge/intent_router.py`, `bridge/prompts.py`. The R2 loaders import the supplier list from `bridge/virtual_owner.py` and the forbidden patterns from `bridge/api.py` until consolidation happens.
  - #2 (FastAPI): NOT in stack. Constitution Section 1.3 reflects this.
  - #3 (Firebase): PENDING. Section 10 reflects this.
  - R3 substrate / R4 self-healer policy: built on propose-then-merge basis. See `bridge/self_build_gate.py`.
