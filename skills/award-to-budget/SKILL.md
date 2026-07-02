---
name: award-to-budget
description: >
  Convert a signed award into the PC1 cost-baseline budget xlsx plus the
  PC2 WBS template. Use when a contract is signed, when the user says
  convert the award to a budget, set up the cost baseline, build the
  project budget, or freeze the baseline. Runs
  takeoff_pipeline/budget_convert.py: contract value minus target margin
  becomes the cost baseline, broken into cost codes that mirror the bid's
  -GP lines, with management reserve as an explicit named line, frozen on
  the Owner's approval (P14). PC1 plus PC2, Prompt 10 of 12, built
  2026-06-12. Pilot: PRJ-2026-ACP-001.
---

# Award To Budget

## Source of record

The budget xlsx in
`Awarded Projects/<project>/09 Financials -GP CONFIDENTIAL/<project-id>_budget_v<NN>.xlsx`
(zero-padded version).
This is a LIVE document per P13: never mirror it to markdown, always read
the xlsx. It is -GP material: internal cost basis, margin, and reserve.
Never client-facing, never emailed externally, never quoted in client
documents. Superseded versions live in `superseded/` next to it; the PC4
reader (`bridge/project_controls.py`) picks the active file from the 09
folder.

## Inputs (all referenced, never embedded, per P10)

- Signed contract value. Source: the executed contract in
  `01 Contract/`. If that folder is empty, STOP and say so: no contract,
  no budget (P14: baselines or nothing). The tool enforces this gate on
  `--project-folder` runs; the `--out <dir> --project-id` mode bypasses
  it and is for scratch output only, never for a real award.
- The bid's -GP report cost lines. Source: the bid folder's `-GP` PDF.
  Transcribe the margin table (Line Item and Cost columns, plus the G&A
  info amount as its own row) into a small csv or xlsx. Quote any cell
  with a thousands comma; the tool refuses rows that spill past the
  headers. Name it plainly (`gp_lines.csv`), never starting with
  "baseline" and never containing "budget" or "baseline" if it is an
  xlsx, and keep it OUT of the 09 folder: the PC4 reader picks its file
  from there by name. Blended rows like "Deck / Joists / Anchors" must
  be itemized first; the tool refuses to split a blend.
- Target margin. Owner sets it at award review. The company net target
  lives in `bridge/bid_rates.py` (`net_target_gp_pct`); per-line GP
  targets live in `BID_MARGINS` in the same file. The numbers stay in
  that file and on the -GP report, never here.
- Management reserve. Owner sets it at award review, as a percent of
  the cost baseline (`--reserve-pct`, same convention as `--margin`: 2
  and 0.02 both mean 2 percent) or a fixed amount (`--reserve-amount`).
  Zero is allowed but must be stated; the tool refuses to default it.

## Margin math (P16: estimate is not budget)

Contract value minus target margin is the cost baseline. Management
reserve is carved out as an explicit named line (MR), never buried in
the codes. The remainder spreads across the cost codes pro-rata by the
source -GP line costs. The scale factor is printed and stamped on the
BUDGET sheet; when it drifts more than 15 percent from 1.0, the tool
warns and the numbers go back to Owner before freeze.

## Cost codes (mirror the -GP lines exactly)

| Code | Line | Note |
|------|------|------|
| FAB | Fabrication | |
| ERE | Erection | |
| JST | Joists | |
| CDK | Composite deck | |
| RDK | Roof deck | |
| ANC | Anchor rods | |
| STR | Stairs | zero when not a -GP cost line |
| MSC | Misc metals | zero when not a -GP cost line |
| SHD | Shop drawings | zero when folded into FAB and ERE rates |
| GA | G&A overhead | from the source G&A row; no WBS line |
| MR | Management reserve | explicit input; no WBS line |

CLO is a schedule-only code on the WBS sheet (closeout carries no cost
line). G&A and MR are budget lines without WBS lines: overhead and
reserve are not scheduled work, so PC4 BAC covers the work codes only.

## Process

1. Confirm the signed contract is in `01 Contract/` and read the
   contract value from it. Confirm target margin and reserve with
   Owner. Ask, do not guess.
2. Transcribe the -GP cost lines to csv (or point at an existing one).
3. Convert:
   `py -m takeoff_pipeline.budget_convert convert --source <lines.csv>
   --contract-value <usd> --margin <pct> --reserve-pct <pct>
   --project-folder "Awarded Projects/<project>"`
   This writes the draft `<project-id>_budget_v<N>.xlsx` with the BUDGET
   sheet (cost baseline by code) and the WBS sheet (P15 template).
4. Fill the WBS template: planned units, planned hours, start and end
   dates from the takeoff and the schedule; split FAB-S1 and ERE-S1 into
   real sequences. WBS budget cells must sum to each work code total;
   one line owns each dollar. The tool never invents quantities.
5. Review with Owner. Check
   `py -m takeoff_pipeline.budget_convert verify <budget.xlsx>` runs
   PASS, including the PC4 loader cross-check.
6. Freeze on the Owner's approval:
   `py -m takeoff_pipeline.budget_convert freeze <budget.xlsx>
   --approved-by "The Owner"`
   The freeze stamps the BASELINE flag cell and the frozen date, then
   moves prior versions to `superseded/`. From then on the file is the
   P14 baseline: edits require a new version (rerun convert), never an
   overwrite. A re-baseline leaves the old frozen file governing PC4
   until the new draft freezes. The freeze gate re-checks the P16 sum,
   refuses formula cells without cached values, checks the BAC
   partition, and refuses incomplete WBS lines unless frozen with
   `--allow-incomplete` (PC4 will flag the gaps).

## WBS template (P15: integrated WBS)

Levels: shop drawings, procurement, fab by sequence/area, delivery,
erection by sequence, deck, closeout. Each line carries scope, budget
cost code, schedule activity, quality check, and risk note together, so
SPI and CPI run per line. Progress types are `production` (count units:
tons, sf, pieces) or `milestone` (rule of credit: issued 20, approved
75, released 100); never mix the two on one line (P17). DEL-01 and
CLO-01 are schedule-only lines; PC4 lists them as data flags until they
carry budget, which is by design, not an error.

## Rules

- Never client-facing. The budget xlsx, the -GP source, and every number
  in them are internal. No supplier names anywhere in the workbook.
- No rates, margins, or contract sums embedded in this skill (P10); they
  live in `bridge/bid_rates.py`, the -GP report, and the signed
  contract.
- No baseline, no variance (P14). A draft has no BASELINE flag and PC4
  refuses it. Freezing is the approval act and records who approved.
- Never overwrite a frozen file. The tool refuses; new numbers mean a
  new version. Drafts overwrite only with `--force`, after a snapshot to
  `_handoff/backups/`.
- All math is deterministic Python in budget_convert.py (constitution
  Section 11); the AI transcribes inputs and reads outputs, it does not
  do the arithmetic.
- Downstream: `bridge/project_controls.py` (PC4 SPI/CPI, PC5 dashboard)
  reads this file. Progress capture lands in the PC3 shop log keyed by
  WBS line.
- No em-dashes in anything this skill produces.
