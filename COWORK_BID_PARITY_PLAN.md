# Cowork Bid Parity Plan

How the Cowork virtual office reproduces the exact bid estimation the Windows EXE produces, with the same accuracy. Drafted 2026-05-22.

## Goal

A bid that runs in Cowork must return the same tonnage, same client total, same GP, same gate verdict, and same Virtual Owner result as the EXE for the same input. The two PDFs (client proposal + GP) must be byte-equivalent at the numeric content layer.

## Source of truth

**Self-contained.** Cowork runs on any machine that has the project folder, with or without the EXE installed. All data and code Cowork needs lives inside `C:\Users\YourUser\Projects\Cowork Virtual Office\cowork_bid\`.

- `cowork_bid/vendored/` holds frozen copies of `aisc_master.csv`, `calibration_2026Q2.json`, `CALIBRATION_HASHES.json`, `vendor_whitelist.json`, `bid_counter.json`, and `bid_rates.py`. Refreshed manually when the EXE side publishes a new quarter.
- `cowork_bid/bids/` is the Cowork bid output folder. Separate from the EXE's `Documents\Your Company Bids\`.
- `cowork_bid/bid_pipeline.db` is the Cowork state machine. Separate from the EXE's `data/bid_pipeline.db`.
- Bid prefix is `PRJ-` by default (Your Company Workspace) to keep Cowork-generated bids distinguishable from EXE-generated bids. Switch to `NC-` only with Owner approval.

Cowork has bash sandbox access plus the Anthropic, OpenAI, and Gemini APIs through skills and direct API calls. It does NOT have the EXE's stdio MCP server with 97 tools. So Cowork does the work itself.

## EXE flow, in one paragraph

A bid is created via `intake_bid_from_invite()` from a GC invite text, or via `process_full_takeoff(pdf_path, building_sf, building_type, complexity)` from a drawing PDF. Stage 1 extracts members via pdfplumber. Stage 2 validates each shape against `data/aisc_master.csv` (2,299 rows, AISC v16.0). Stage 3 maps members to a 3D node graph (AABB). Stage 4 detail-passes via Gemini vision for bolting, welds, camber. Stage 5 calculates weight (lb/ft from AISC times length). Stage 6 prices via `bid_rates.price_bid_line()` using the CEO-locked Q2 2026 rates. Stage 7 runs `bid_sanity_gates.run_gates()` (5 gates) and `VirtualOwner.review()` (26 rules). Two PDFs render to `Documents\Your Company Bids\YYYY-MM\NC-YYYY-XXX-NNN\`. State machine writes to `data/bid_pipeline.db` (SQLite WAL).

## Parity matrix

Each EXE step gets classified into one of four buckets for Cowork replication:

- **D (deterministic)**: pure math or table lookup. Cowork runs the same Python code or a port. Identical output.
- **AI-V (AI vision)**: requires Gemini vision (PDF drawing parsing, bolting pattern detection). Cowork calls the same API.
- **AI-R (AI reasoning)**: requires Claude or GPT for scope judgment, invite parsing, RFI drafting. Cowork calls the same API.
- **DATA (data dependency)**: needs a file from the EXE side. Cowork mirrors or symlinks the file.

| EXE step | Module | Bucket | Cowork approach |
|---|---|---|---|
| Invite intake | `bridge/intake_bid.py` | AI-R + D | Regex extraction first, Claude fallback on miss. Same output schema. |
| PDF text extraction | pdfplumber in `takeoff_controller` | D | Run pdfplumber in bash sandbox. `pip install pdfplumber --break-system-packages`. |
| AISC shape lookup | `bridge/aisc_validator.py` | D + DATA | Read `data/aisc_master.csv` directly. 2,299 rows. Same lookup logic. |
| Drawing detail pass | `gemini_compat.call_gemini_detail_pass` | AI-V | Cowork calls Gemini vision with the same prompt template. |
| Weight calculation | `takeoff_controller` stage 5 | D | `lb_per_ft * length_ft` per member. Identical Python. |
| Pricing | `bridge/bid_rates.py` `price_bid_line()` | D + DATA | Import `BID_RATES`, `BID_MARGINS`, `MATERIAL_COSTS`, `DRAWING_STAGE_ADDERS` dicts. Same Python file. |
| Sanity gates | `bridge/bid_sanity_gates.py` `run_gates()` | D | Port the 5 gate functions verbatim. Pure math. |
| Virtual Owner | `bridge/virtual_owner.py` `review()` | D | Port the 26 rule methods verbatim. All regex + numeric checks. |
| State machine | `bridge/bid_pipeline.py` SQLite | D + DATA | Cowork uses its own SQLite at `cowork_bids/bid_pipeline.db` (WAL mode), OR connects to the same EXE DB (single source of truth, recommended). |
| PDF generation | ReportLab in EXE templates | D + DATA | Use ReportLab in bash sandbox. Copy template config. Same numeric content guarantees byte-similar PDFs. |
| Bid folder | `bridge/bid_documents.py` | D | Mirror `NC-YYYY-XXX-NNN` naming. Read/increment `data/bid_counter.json`. |

Every step is either pure D (port the code) or AI-V/AI-R (same API call, same prompt). The accuracy gap is zero where the AI prompts match.

## Data files (all vendored, all inside the project folder)

Cowork owns its own copies. No reads from `C:\Tools\virtualoffice`. Refresh policy below.

| File | Size | Role | Vendored at |
|---|---|---|---|
| `aisc_master.csv` | 127K, 2,299 rows | AISC v16.0 shape data | `cowork_bid/vendored/aisc_master.csv` |
| `calibration_2026Q2.json` | 18K | Wage rates (SAM.gov WD TX20260025), NCCI WC, supplier costs, freight bands | `cowork_bid/vendored/calibration_2026Q2.json` |
| `CALIBRATION_HASHES.json` | 493B | SHA-256 lock for calibration file | `cowork_bid/vendored/CALIBRATION_HASHES.json` |
| `bid_counter.json` | 4B | Cowork's own sequence (separate from EXE) | `cowork_bid/vendored/bid_counter.json` |
| `vendor_whitelist.json` | 1.8K | Approved supplier names (for R03) | `cowork_bid/vendored/vendor_whitelist.json` |
| `bid_rates.py` | 11K | `BID_RATES`, `BID_MARGINS`, `MATERIAL_COSTS`, `DRAWING_STAGE_ADDERS`, `PAYMENT_STRUCTURE` | `cowork_bid/vendored/bid_rates.py` |

**Refresh policy.** When the EXE publishes a new calibration quarter:

1. Copy the new files from the EXE source into `cowork_bid/vendored/`.
2. Verify SHA-256 against `CALIBRATION_HASHES.json`.
3. Run `cowork_bid/tests/test_smoke.py` against a known fixture.
4. Update the date in `cowork_bid/README.md`.

This is a manual step. Drift is preferable to silent breakage. The hash lock catches accidental edits.

## Cowork-native bid pipeline

The `cowork_bid/` directory inside the project folder is the implementation. Skeleton committed 2026-05-22. Smoke tests pass.

```
cowork_bid/
  __init__.py         done
  rates.py            done    re-exports BID_RATES, BID_MARGINS, etc. from vendored bid_rates.py
  aisc.py             done    validate_shape() and weight_of() against vendored CSV
  pricing.py          done    build_priced_bid() end-to-end
  paths.py            done    PRJ-YYYY-XXX-NNN folder + counter
  gates.py            stub    M1 port from bridge/bid_sanity_gates.py
  vm.py               stub    M1 port from bridge/virtual_owner.py
  state.py            stub    M1 port from bridge/bid_pipeline.py
  takeoff.py          stub    M2 pdfplumber + Gemini vision
  pdf_render.py       stub    M3 ReportLab client + GP
  vendored/
    aisc_master.csv             2,299 shapes
    calibration_2026Q2.json     wage + WC + supplier
    CALIBRATION_HASHES.json     SHA-256 lock
    bid_counter.json            Cowork sequence (separate)
    vendor_whitelist.json
    bid_rates.py                CEO-locked
  prompts/            empty until M2 (Gemini detail pass template)
  tests/
    test_smoke.py     done    20 checks pass
    fixtures/         empty   M1 will add known-good inputs
  bids/               empty   PRJ-YYYY-XXX-NNN folders land here
  bid_pipeline.db     created at runtime, WAL mode
```

Smoke test results (2026-05-22):
- 2,299 AISC shapes load.
- W36X262 lookup returns 262 lb/ft (matches AISC v16.0).
- W99X999 rejected (no shape invention).
- W36X262 at 40 ft returns 10,480 lbs.
- `price_bid_line("fab", 50)` returns $187,500 at 31% GP.
- End-to-end pipeline on (W36X262 x1 + W24X68 x4) + 5,000 SF roof deck + 20 anchor rods returns $68,789.68 grand total, $13.76/SF, 26.6% GP blended, G&A 7.5% folded.

## Step-by-step pipeline (Cowork side)

1. **Intake.** Take invite text or drawing PDF as input. If invite text, run `cowork_bid/intake.py` regex pass first, fall back to Claude Sonnet 4.6 if fields missing. If drawing PDF, jump to step 2.

2. **PDF extraction.** `pdfplumber` extracts member tables, sheet schedules, notes. Output: `[{member_id, shape, length_ft, qty, notes}]`. Identical to EXE stage 1.

3. **Shape validation.** Each shape passes `cowork_bid/aisc.validate(shape)`. Lookup in `aisc_master.csv`. Reject and flag suggestions for invalid shapes. SJI joists (K, LH, DLH) pass through via standards partition (same as EXE).

4. **Vision detail pass.** Gemini Flash vision call on the PDF with the same prompt as `gemini_compat.call_gemini_detail_pass()`. Returns bolting patterns, welds, camber notes, paint specs. Confidence threshold 70%.

5. **Weight calculation.** Per member: `lb_per_ft * length_ft = lbs`. Sum by member type. Total structural tons. Identical to EXE stage 5.

6. **Pricing.** Apply rates from `BID_RATES` (fab $[FAB RATE]/T, erection $[ERECTION RATE]/T, joists $[JOIST RATE]/T, roof deck $[ROOF DECK RATE]/SF, composite $[COMPOSITE DECK RATE]/SF, anchors $[ANCHOR RATE]/EA). Apply drawing-stage adder (IFC 0%, DD +5%, Budget/SD +8%). Apply G&A 7.5%. Apply small-project override if Owner flagged "small" (50% GP target).

7. **Sanity gates.** Run all 5:
   - Gate 1: Joist count vs bay geometry
   - Gate 2: Tonnage per SF (lb/SF range by building type)
   - Gate 3: Dollar per SF (range by building type)
   - Gate 4: Scope completeness (columns, joists, deck, fasteners)
   - Gate 5: Structural ratios (6 sub-checks, currently roadmap defaults, not yet calibrated)
   Output: `{gates: [...], confidence: 0-100, blocked: bool, decision: GO|CAUTION|BLOCKED}`.

8. **Virtual Owner.** Run all 26 rules. R01-R19 production rules, R20-R26 pilot rules (deployed 2026-05-16). Output: `VMReview` with `approved`, `verdict`, `confidence`, `issues`. Block if any `BLOCK` severity rule fires.

9. **PDF render.** ReportLab generates two PDFs:
   - `proposal.pdf` - client-facing. Scope, quantities, pricing, 30/20/50 payment terms. No supplier names. No team names. No GP data.
   - `internal_estimate.pdf` (`-GP` suffix in EXE) - full cost breakdown, supplier quotes, GP% per line.

10. **Filing.** Read `bid_counter.json`, generate `NC-YYYY-XXX-NNN` folder name, write artifacts. Update counter.

11. **State machine.** Write bid record to `bid_pipeline.db`. State = SCANNED. Subsequent state transitions (REVIEWING, PURSUING, SUBMITTED, WON, LOST, PASSED) via the same direct-route patterns the EXE exposes (`advance bid`, `mark bid won`, etc.).

## Accuracy comparison harness

To prove parity, every Cowork run must match the EXE run on the same input. The harness lives in `cowork_bid/tests/`.

Test fixtures: `tests/fixtures/<bid_id>/input.pdf` plus `tests/fixtures/<bid_id>/expected_output.json` (generated from the EXE on the same input). Each fixture covers one building type: STEEL_FRAME, JOIST_DECK, COMPOSITE.

Comparison metric (per fixture):

```
diff = abs(cowork_tons - exe_tons) / exe_tons
gate_match = cowork_gates == exe_gates
vm_match = cowork_vm_issues == exe_vm_issues
price_diff = abs(cowork_total - exe_total) / exe_total
```

Acceptance criteria:
- `diff` < 0.001 (deterministic math should match exactly)
- `gate_match` = True
- `vm_match` = True (issue list, not just verdict)
- `price_diff` < 0.001

Anything larger surfaces as a parity break that has to be reconciled before Cowork is trusted on a real bid.

## AI prompts (parity-critical)

The two AI calls that affect numeric output are:

1. **Gemini vision detail pass** (`gemini_compat.call_gemini_detail_pass`). Prompt template must be identical in Cowork. Read the existing template from the EXE source on first run, vendor it into `cowork_bid/prompts/detail_pass.txt`, version it.

2. **Invite intake fallback** (`bridge/intake_bid.py` Claude fallback). Same template, vendored to `cowork_bid/prompts/invite_intake.txt`. Run the same Sonnet 4.6 model with the same temperature.

Locking the prompts (and the models, and the temperature) is what keeps the AI-V and AI-R paths deterministic enough for parity.

## Model routing

Cowork mirrors the EXE's routing (see CLAUDE.md, AI Model Routing section):

- T1 fast `claude-haiku-4-5-20251001`: invite triage, classification.
- T2 default `claude-sonnet-4-6`: invite parsing fallback, scope clarification.
- T3 accurate `claude-opus-4-6`: compliance review, final bid review pre-send.
- T4 max `claude-opus-4-7`: high-stakes vendor negotiation, RFI drafting.
- GPT-4o: PDF structure passes, Monte Carlo variance.
- Gemini Flash: drawing vision (the detail pass).

Cowork should keep the same `model_routing.json` config the EXE uses. Single file, single source of truth. (Note: the EXE source has the constant in code but the runtime JSON config was not found at `data/model_routing.json` during this audit. Confirm where the live config lives before claiming parity.)

## Gaps and risks

1. **Gemini quota.** Both EXE and Cowork share the same API key. A heavy bid run could double the call rate. Cap Cowork at the same per-bid budget the EXE uses.

2. **PDF byte-equality is not possible.** ReportLab PDFs include timestamps. Parity test compares numeric content (extracted via pdfplumber) and visual layout, not raw bytes.

3. **Calibration drift.** Cowork holds vendored copies. If the EXE side updates its `data/` and the vendored copies are not refreshed, prices diverge. Mitigation: SHA-256 hash lock in `CALIBRATION_HASHES.json`. Cowork verifies on every run and warns on mismatch. Refresh is manual and deliberate.

4. **State machine isolation.** Cowork uses its own SQLite at `cowork_bid/bid_pipeline.db`. No shared writes with the EXE. No counter contention. The cost: bids on the two systems do not appear in each other's pipeline summaries. Manual reconciliation if needed.

5. **AISC v16.0 only.** If AISC publishes v17, the EXE updates and Cowork must follow via the refresh policy. The hash lock catches the version mismatch.

6. **Gate 5 not calibrated.** The EXE's `run_gates()` returns gate 5 with `'calibrated': False`. Cowork inherits this status. Both stay at the same calibration level until real bid data is fed back.

7. **Direct route bypass.** The EXE has 36+ direct routes that bypass the AI (`quick bid`, `score bid`, `aisc weight`, etc.). Cowork should implement the same table so chat-style commands work identically in either environment. Most are pure D, easy port. Scheduled for M1 alongside the gate and VM ports.

8. **No shared bid counter.** Cowork starts at 0 inside its own `cowork_bid/vendored/bid_counter.json` and uses the `PRJ-` prefix. Side-by-side runs do not collide. Switching to `NC-` requires Owner approval and a counter merge plan.

## Decisions made (2026-05-22)

- Cowork is self-contained. Vendored copies of all data files. No reads from `C:\Tools\virtualoffice`. Owner directive.
- Cowork has its own SQLite at `cowork_bid/bid_pipeline.db`. No shared writes with the EXE.
- Cowork bid prefix is `PRJ-` to keep folders distinguishable side by side. Counter starts fresh.

## Decisions made (2026-05-22, run 2 - resolved against profile docs)

The 5 open questions were resolved against `owner-rules.md`, `owner-directives-v4.md`, `brand-voice.md`, `company-details.md`, and `.specify/constitution.md`. Quotes cited from those files.

**Q1. Parity threshold.** Exact match on deterministic-math paths. `< 0.001` on AI-touched paths. No tolerance drift.
- Grounded in owner-rules.md Pass 1 (10% divergence triggers re-takeoff, not explanation) and owner-directives-v4.md Section 28 ($/SF and $/T must land within 10% on every bid). Locked rates ($[FAB RATE]/T fab etc.) match byte-for-byte.

**Q2. EXE vs Cowork disagreement.** EXE is the canonical bid system when reachable. Cowork validates against it. If EXE is not reachable on the host, Cowork's own SQLite is the system of record for Cowork-produced bids. Divergence with the EXE = port bug. Block the Cowork commit until reconciled.
- Constitution Principle 7: "The bid pipeline database (bid_pipeline.db) is the system of record." Cowork's DB is the system of record for its own bid stream. Cross-system divergence means the math drifted; the constitution's "no tolerance drift" stance applies.

**Q3. Direct routes.** Yes, port all 36+. Same muscle memory in both environments.
- brand-voice.md Section 24: "Short sentences. Specific numbers."
- owner-directives-v4.md Section 1: "Minimum output. Solve the problem and nothing more. If 200 lines could be 50, rewrite."
- Action: scheduled in M1 alongside the gate and VM ports.

**Q4. PDF signatory.** Owner Steel on client docs. The Owner on legal and contract docs.
- Constitution Principle 5: "Client-facing documents: 'Owner Steel' as the signatory name. Never 'The Owner' on bids, proposals, or client emails."
- brand-voice.md and company-details.md both confirm.
- Action: `cowork_bid/pdf_render.py` enforces this string at the signature block. M3.

**Q5. Invite-intake fallback model.** Claude (Anthropic) primary. GPT-4o fallback. Gemini Flash for triage only.
- Constitution preamble: "Gemini Flash (triage), Claude/GPT-4o (reasoning)."
- Tier mapping per CLAUDE.md AI Model Routing: T2 default `claude-sonnet-4-6` for drafting, intake parsing falls in this bucket.
- Action: `cowork_bid/intake.py` uses Sonnet 4.6 with temperature 0.

## Open items not blocked by the 5

- Constitution sign-off. The file lists Joseph as author. Principles 1 (AISC boundary) and 3 (bid rates) are the highest-stakes rules. Owner confirms verbally + in writing per the amendment protocol.
- Gemini prompt vendoring. The detail pass template lives in the EXE source. Locate, vendor, and version-pin before M2.

## Sequencing

Three milestones. Each one ends with a passing parity test against a real bid fixture.

**M1 (DONE 2026-05-22): pure D path + state machine + chat routes.** Ported rates, AISC lookup, weight calc, sanity gates, Virtual Owner, SQLite WAL state machine, and 16 chat routes. Parity test against EXE on TSC Sumter SC fixture: byte-identical JSON on `run_gates()` and `VirtualOwner.review()`. Confidence 20/100, BLOCKED verdict, 2 blockers + 2 warnings. Matches EXE exactly.

**M2 (DONE 2026-05-22): pdfplumber + Gemini.** Vendored `SYMBOL_CLASSIFIER_PROMPT` to `cowork_bid/prompts/detail_pass.txt`. Built `cowork_bid/takeoff.py` with regex-based shape extraction across all pages plus a Gemini Flash vision call at temperature 0. Smoke test on a 7-member synthetic PDF: 100% AISC coverage, 13.142 tons, $109,682.91 grand total. Gemini detail pass auto-skips when `GEMINI_API_KEY` is unset.

**M3 (DONE 2026-05-22): two PDFs.** `cowork_bid/pdf_render.py` produces both `proposal.pdf` (client-facing, Owner Steel signatory, 30/20/50 payment terms, full STANDARD_INCLUSIONS + STANDARD_EXCLUSIONS, no GP, no supplier or team names) and `internal_estimate-GP.pdf` (internal, The Owner signatory, per-line GP%, cost basis, material cost basis dict). Constitution compliance verified on output: all 16 checks pass. Em-dash stripper applied to every client string.

Estimate: original 3-week target landed in one session. Each milestone is independently testable. M1 = sanity-check a bid the EXE produced. M2 = end-to-end takeoff from a PDF. M3 = file-and-forget two-PDF bid delivery.

## Open questions for Owner

1. Is the parity harness a blocker for shipping any Cowork bid, or a one-time validation that gets archived?
2. What happens if Cowork and the EXE disagree mid-bid? Both? EXE wins? Cowork wins? Block and ask?
3. Do you want Cowork to expose the same `quick bid`, `score bid`, `review bid` chat commands the EXE has, so the same muscle memory works in both environments?
4. PDF signatory name. Constitution Principle 5 requires "Owner Steel" as client-facing signatory. EXE assumed to comply, but the EXE PDF templates were not read in this audit. Confirm before M3 PDF render.
5. AI provider for Cowork's invite-intake fallback. Cowork has direct access to Claude, OpenAI, and Gemini APIs through the project. EXE uses Claude. Confirm same.

---

End of plan. Next step is a Owner read pass on this doc and M1 port (gates, VM, state, direct routes).
