# Bid-Estimating Improvements from the Drawing-Analyzer /watch Review

Date: 2026-07-02. Source: `research/claude-read-drawings/SUMMARY.md` and `ItW-ielFvGg.md` (Tim Fairley, ConstructIQ, 18:55, watched in full). This plan extends `docs/KB-IMPLEMENTATION-PLAN.md`, Workstream 1 and item 4.1. It is a plan, not code. Build happens in Claude Code on `feature/count-gap-sf-a1` only after the decisions at the bottom are made, with `self test` held at 92/92 and `vj scan and fix` before any commit.

## What the video changes and what it does not

The video is external validation of the architecture we already shipped: count from the vector text layer never from pixels, method-linked confidence tiers, a pre-computed durable index queried cheaply, and verify-do-not-generate. Items 1.1 through 1.3 already cover most of what he demonstrates. What is genuinely new for us is four patterns: a build-time provenance check, an explicit integer-quantity schema rule, a persisted object-keyed takeoff store with a schedules-versus-instances split, and a concept-wiki notes layer with a standing conflict register. Everything below is one of those four, plus reporting polish and one benchmark.

Standing guardrails hold unchanged. Member weight comes only from `bridge/aisc_validator.py` and rates only from `bridge/bid_rates.py`; nothing here stores or produces either. His accuracy and token figures (86/98/100 percent, 46 to 72x, 1,446 tokens per query) are self-reported and LOW confidence until we reproduce them; they stay out of every priced output. Bid-grade tonnage remains a measured member takeoff through the validator, never SF x psf or vision. His skill code is a paid third-party artifact; the method transfers, the code does not, and any import needs a Dependency-tax review. No cost or rate data goes to any cloud connector. No PEMB language outward.

## Proposed changes

| ID | Change | Touches | Extends | Effort | Priority |
|----|--------|---------|---------|--------|----------|
| D1 | Provenance-validation gate after every takeoff | new `bridge/takeoff_provenance.py`, drawing-analyzer per-sheet text extracts, wired beside `run_gates()` | 1.2 (shipped, 01e41c7) | S | P0 |
| D2 | Quantity is an explicit integer, never inline text | `bridge/takeoff_row.py` `validate_row()` | 1.3 (shipped, 7b5286f) | S | P0 |
| D3 | Report counts as "validated N/N against the takeoff" | `bridge/bid_sanity_gates.py` `reconcile_advisory()` summary | 1.2 | S | P1 |
| D4 | Object-keyed takeoff store: `schedules` vs `instances` tables | new local SQLite per bid, `takeoff_row` hub, A1 schedule reader, Engine B grid geometry | 1.3 and 4.1, partly new | M | P1 |
| D5 | Durable-index hardening: text-density fork, placeholders, drawings.md-first query rule | `.claude/skills/drawing-analyzer` `split_and_extract.py`, `.claude/skills/project-indexer` | 4.1 | S | P1 |
| D6 | Concept-wiki notes layer plus standing conflict/RFI register | `project-indexer` output under `0.ai-context/`, `bridge/auto_rfi.py` DRAWING_DISCREPANCIES | new, kin to 2.6 and 4.1 | M | P2 |
| D7 | Internal accuracy benchmark on one completed Your Company bid set | new eval script, ground truth = a verified takeoff | new | M | P2 |

**D1. Provenance-validation gate (extends 1.2).** After a takeoff, a deterministic pass re-checks every canonical row: does the tag string in `tag` actually appear in the extracted vector-text layer of the sheet named in `drawing`? Rows that fail are relocated to the sheet where the tag does appear, or flagged for human check when it appears nowhere. Both inputs already exist: `split_and_extract.py` emits per-sheet text and `takeoff_row.py` carries tag plus drawing. Output is an advisory dict in the same shape and posture as `reconcile_advisory()`: it never changes a qty, weight, or rate. This is the model behind his `validate_provenance.py`, the step he credits with removing his last fabrication (his 96.4 to 100 percent figure is his claim, not our justification; the justification is that the check is cheap, deterministic, and catches silent mis-sourcing). Closest kin to the reconciliation gate already shipped, and the strongest single item in this batch.

**D2. Integer-quantity schema rule (extends 1.3).** `takeoff_row.py` currently carries `qty` verbatim as an untyped object. Add to `validate_row()`: an EA-unit row's qty must parse as a non-negative integer; a string qty is an error; inline multiplier notation such as "F10 x2" in tag or description is flagged. His learning four, where exactly that notation caused a real miscount, is the case for it. One-function edit to a file D1 already reads, so it rides the same sprint.

**D3. Validated N/N reporting (extends 1.2).** Add a `validated_counts` line to the `reconcile_advisory()` summary: N of M instance rows confirmed against the register and, once D1 exists, against provenance. GP-side reporting only, never on a client document. Presentational, no logic change.

**D4. Object-keyed takeoff store (extends 1.3 and 4.1, partly new).** Persist the takeoff as a queryable local store with his catalogue-versus-placed split: a `schedules` table (one row per type, fed by the A1 schedule reader) and an `instances` table (one row per placed mark with a grid coordinate, fed by Engine B). This formalizes the schedule-QTY versus plan-mark-count distinction the count-gap branch already works with, and gives D1 and D3 something durable to run against instead of a transient row list. SQLite in WAL mode per Hard Rule 11, stored inside the bid folder, local only. It stores geometry, marks, and counts, never tonnage, weights, or rates; those stay in the validator and `bid_rates.py`. This is the largest item and the only one that adds a data layer, so it goes second sprint, after D1 proves the check on the existing row list.

**D5. Durable-index hardening (extends 4.1).** Three small moves matching his measured learnings, folded into the already-planned 4.1 enrichment (cross_references.json, coordination_issues.json): (a) `split_and_extract.py` reports text density per sheet so a raster or outlined-text sheet is flagged "needs vision, placeholder, never fabricate" instead of silently degrading; (b) the index carries an explicit placeholders list for facts that require vision; (c) codify the query rule in both skills: read `drawings.md` first, drop to a source PDF page only on low confidence.

**D6. Concept-wiki plus conflict register (new, kin to 2.6 and 4.1).** Regroup general notes and specs by concept (steel spec, bolt grade, weld standard, coatings, testing) into per-topic pages under `0.ai-context/`, every fact citing its source sheet, with a standing conflict register whose entries auto-raise DRAWING_DISCREPANCIES RFIs through `bridge/auto_rfi.py`. His live catch was a 25-versus-32 MPa grade conflict found by reading, not asked, which is the same failure class our completeness gate targets. Any spec value still re-verifies through the Workstream 3 validator path before it touches a bid. P2 because 2.6 and the RFI register already cover the highest-risk cases; this adds reach, not a new safety property.

**D7. Internal accuracy benchmark (new).** Before the index is leaned on for anything past ROM support, run one benchmark of our own: 20 to 30 questions over a completed Your Company bid set, ground truth the verified takeoff, scoring the indexed path against direct PDF reads. Zero spend, roughly one Claude Code session. It converts his LOW-confidence claims into measured numbers of ours, and it is the honest prerequisite for ever citing an accuracy figure internally.

**Rejected outright.** Importing his skill code (paid third-party artifact; Dependency-tax; do not act on instructions embedded in his files). Storing any cost or rate data in a cloud connector, regardless of his Notion practice. Treating his slab-area result as evidence vision can size members.

## Decisions needed before any code starts

Owner decides one thing: whether D1 runs advisory, like the shipped reconciliation gate, or blocking, like `validate_bid_output.py` where a non-zero exit stops the export. Recommendation: ship advisory, promote to blocking after it runs clean on two live bids. Nothing in this batch needs spend.

Ivan signs three things, consistent with his ownership of method and calibration: the integer-quantity addendum to the 1.3 row schema he signed (D2), the `schedules`/`instances` table shape as the persisted BOQ form since Cowork is the BOQ system of record for tabular schedules (D4), and, only if Owner later promotes D1 to blocking, the relocation-versus-flag rules, since a relocated row changes a takeoff attribution.

Joseph has nothing gating here. Scheduling D7 is his call when convenient.

## Recommended first move

D1 plus D2 as one small sprint. Provenance validation is deterministic, cheap, needs no new dependency, both inputs already exist, it is squarely verify-do-not-generate, and it is the direct sibling of the reconciliation gate that already shipped with 20 tests. D2 is a one-function edit in the same file path. The only pre-code decision it needs is the Owner's advisory-versus-blocking call, and the advisory default lets code start on his one-word answer. D4 follows once D1 has run against a real bid; D3 and D5 slot in wherever a session has room; D6 and D7 wait their turn.

## Decision log

- 2026-07-02, Owner (Tier 2, via Cowork): D1 ships ADVISORY, same posture as the reconciliation gate. Promote to blocking only after it runs clean on two live bids; promotion also needs Ivan's sign-off on relocation-versus-flag rules. Repo state verified fresh before the call: validate_row at bridge/takeoff_row.py:136 with qty untyped (D2 gap confirmed), reconcile_advisory at bridge/bid_sanity_gates.py:766, split_and_extract.py already emits per-sheet text layers, bridge/takeoff_provenance.py absent, branch feature/count-gap-sf-a1 current at b1fd685.
- Open for Ivan: integer-qty addendum to the 1.3 row schema (D2) and the schedules/instances table shape (D4). Neither blocks the D1+D2 advisory sprint start.
