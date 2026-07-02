# Knowledge Base Implementation Plan

Source material: three /watch knowledge bases produced in Claude Code, June 2026.
- docs/AISC-EDU-KB.md (270 AISC Education videos triaged, 232 watched, full SYNTHESIS).
- research/constructiq-watch/ (15 ConstructIQ videos, SUMMARY.md).
- docs/IMAGE-GEN-KB.md (free vs paid image generators, Your Company scope).

This plan converts the recorded findings into actionable work. It does not change any
locked value. Nothing here is implemented yet. Each item names an owner, an effort, a
priority, and any decision gate. Code items are built in Claude Code on the existing
feature/count-gap-sf-a1 branch where noted.

## Guardrails that bound every item below

These come straight from the KBs and they agree with current Your Company doctrine.
- Verify, do not generate. AI checks money work, it never sets the system-of-record
  number. Member weight stays in bridge/aisc_validator.py. Rates stay in
  bridge/bid_rates.py. Every spec number, table, washer size, edge distance, or grade
  spoken in a video is a study aid, re-verified before it touches a bid or a stamp.
- The single biggest external finding: ConstructIQ independently arrives at our exact
  "verify, do not generate" posture from the general-construction side. This validates
  the architecture. It does not loosen it.
- Confidentiality. No MATERIAL_COSTS, supplier names, or BID_RATES in any cloud
  connector (Notion, Airtable, and so on). ConstructIQ stores cost data in cloud Notion,
  which for us is a Tier 1 violation. Keep cost and rate data local.
- Firewall and brand. Supplier and mill names from the videos are internal estimating
  inputs only, never on a proposal, GP report, or capability sheet. No PEMB or
  metal-building language outward. Bridge content (AASHTO, AWS D1.5) stays out of an
  AISC 360 building bid.
- AISC Manual edition gap. Many useful entries were recorded against the 15th edition.
  aisc_validator.py wraps v16.0, and the 16th edition rebases connection-material tables
  from 36 ksi to 50 ksi. No 15th-edition table number or default Fy is a bid input until
  re-confirmed against the current Manual and the validator.

## Workstream 1 - Takeoff and pricing accuracy (highest dollar impact)

The headline finding across the AISC corpus: member tonnage is the smaller half of cost.
The erected-steel cost pie is roughly material 28 percent, fabrication 46 percent,
erection 26 percent, and connection material alone runs 5 to 30 percent of total tonnage
that the validator does not carry. Treating connections as a flat per-ton allowance
under-prices the bid. This workstream makes connection steel and connection labor
first-class, itemized scope.

| ID | Action | Source | Owner | Effort | Priority | Decision gate |
|----|--------|--------|-------|--------|----------|---------------|
| 1.1 | Add a connection take-off pass: every braced bay, moment joint, splice, base, and AESS face carries a separate connection-material and connection-labor line. Validator carries shapes, not gussets, doublers, stiffeners, reinforcing bars, or weld volume. Treat any flat per-ton connection allowance as ROM and flag it. | AISC Ivan callouts | CC + Ivan | L | P0 DONE | DONE 2026-06-29. Connection-pricing method Ivan-signed; rate composition (fab plus erection blended) Owner-confirmed. Allowance pass sizes the line from locked-calibration pct times aisc_validator tonnage times bid_rates rate, ROM and flagged, no number from the model. |
| 1.2 | Reconciliation pass as an advisory gate. A stored skill diffs the finished steel estimate against an AI-extracted requirements and exclusions register and reports coverage rate plus named gaps. Wire alongside run_gates(). Generation off, cross-check on. Best run in a fresh memoryless session. | ConstructIQ 7.1 | CC | M | P0 DONE | DONE 2026-06-29, commit 01e41c7 on feature/count-gap-sf-a1, self test 92/92, 20 tests. Advisory only, cannot change a number |
| 1.3 | Adopt the row-level takeoff schema: Tag, Description, System, Qty, Unit, Drawing, Method, Confidence, Basis, Notes. Attach a written assumption string to every inferred line and a method-linked confidence tier (High vector or text tag, Med schedule read, Low vision or inferred). | ConstructIQ 7.3, 7.5 | CC + Ivan | M | P0 | Ivan confirms the schema matches the BOQ system of record |
| 1.4 | Encode secondary-quantity formulas into the count-gap engine as re-verified study aids: connection material as a tonnage percentage, Whitmore 30-degree spread, shear-lag U = 1 - xbar/L, effective hole diameter +1/8 in, A1085 vs A500 0.93 wall factor, gusset-to-beam fillet +25 percent for non-uniform force, thermal growth ~1/8 in per 100 ft per 15 degrees, L/b over 80 temporary-bracing screen, about 1 hour per connection engineering basis. Each shapes a count, never a final capacity or weight. | AISC Ivan callouts | CC | M | P1 | None. Outputs are flagged, not priced silently |
| 1.5 | Encode the fence-post count rule bars = ROUNDUP(span / spacing) + 1 and schedule-mark reading in the A1 schedule reader and Engine B grid geometry, for secondary steel and rebar. US-convention weights only, never the presenter's metric N-convention figures. | ConstructIQ 7.4, rebar video | CC | S | P1 | None |
| 1.6 | Dollar-threshold escalation table for human review, and ROM output labeled budget-only (minus 20, plus 30 percent), never lump sum. | ConstructIQ 7.7 | CC + Owner | S | P1 | Owner sets the dollar thresholds |
| 1.7 | Splice-method sensitivity flag. The bolted-versus-welded splice assumption swings tonnage and bolt count materially (a worked W14x730 chord: ~70 lb weld metal versus ~6,900 lb steel and 128 bolts). Surface the assumption as an explicit, confirmable input. | AISC Ivan callouts | CC + Ivan | S | P1 | None |

## Workstream 2 - Scope-gap and RFI automation

The recurring root cause of a wrong connection price is incomplete EOR force data. These
become a connection-information completeness gate that runs before pricing, plus an RFI
register generator. Extends the existing takeoff-completeness-check and
scope-creep-detector skills.

| ID | Action | Source | Owner | Effort | Priority | Decision gate |
|----|--------|--------|-------|--------|----------|---------------|
| 2.1 | RFI: missing transfer forces. Transfer force does not equal member axial load unless the bay is unbraced. Request true transfer forces from the SER per COSP 3.1.2. Never let Tekla substitute full member axial. | AISC | CC + PE | M | P0 | None |
| 2.2 | RFI: envelope-loading confusion and eccentric work lines (an 8-inch offset generated 347 ft-k with no moment listed). Trigger a confirm-true-forces RFI and possible member up-size. | AISC | CC + PE | M | P1 | None |
| 2.3 | RFI: seismic system confirmation. Read SDC and R off the structural notes first. Confirm SFRS, R, demand-critical welds, protected zones, and the prequalified AISC 358 connection before bidding. Houston is mostly SDC A or B, R = 3 undetailed; out-of-region jobs pull in 341/358 and AWS D1.8 as real adders. | AISC | CC + Ivan | M | P0 | None. Thresholds CONFIRMED by Owner 2026-06-29: high-seismic on SDC C through F or R greater than 3; Houston SDC A or B with R = 3 treated as complete. No longer pending Ivan. |
| 2.4 | RFI: AESS category per face per COSP 10.2 (cat 1 within touch, 2 within 20 ft, 3 above 20 ft). AESS escalates labor, not tonnage. A set that says AESS without naming items needs a clarification before any blast or finish line is priced. | AISC | CC | S | P1 | None |
| 2.5 | RFI: surface-prep class (SP 6 commercial vs SP 10 near-white) and stair, platform, and drift bracing not shown on incomplete sets. If it is not shown, it is not in the price. Carry both LOW until confirmed. | AISC | CC | S | P1 | None |
| 2.6 | Drawing-completeness gate before pricing. Refuse to price incomplete connection information. Treat general-note connections and blanket full-strength specs as low-confidence RFI items, never silent assumptions. Pair with the existing SF and gross-area confirmation RFI. | AISC + house doctrine | CC | M | P0 | None |

## Workstream 3 - Spec and material doctrine guards (encode into the validator path)

These lock named rules into aisc_validator.py lookups and a doctrine reference, so a grade
or anchor callout is never trusted from an LLM string.

| ID | Action | Source | Owner | Effort | Priority | Decision gate |
|----|--------|--------|-------|--------|----------|---------------|
| 3.1 | Anchor-rod rule. Never call out "A325 anchor bolts" (the supplier quietly furnishes A449). Default F1554 Grade 55 with supplement S1 weldable so a low-set rod can be field-corrected. Flag any Grade 105 callout as field-uncorrectable. Carry the F1554 color code (A36 blue, Gr 55 yellow, Gr 105 red). Build an anchor-callout linter. | AISC, Carter and Kruth | CC + Ivan | M | P0 | Ivan approves the linter rules |
| 3.2 | Lock current material grade defaults into validator lookups: A992 for W shapes, A572 Grade 50 for HP and the 16th-edition connection-material basis, A500 Grade C at 50 ksi rectangular HSS and 46 ksi round, A53 Grade B at 35 ksi pipe (not interchangeable with round HSS), A513 banned for handrail (no minimum strength). | AISC | CC + Ivan | M | P1 | Ivan confirms against current calibration |
| 3.3 | Manual edition-gap guard. Flag any 15th-edition table number, washer size, edge distance, or default Fy spoken in a source until re-verified. Ensure the connection-material basis uses the 16th-edition 50 ksi rebasing, not a 36 ksi default. | AISC | CC | S | P1 | None |
| 3.4 | Bridge-versus-building firewall classifier. Tag AASHTO and AWS D1.5 content as reference-only and keep its fatigue categories and load factors out of any AISC 360 building bid and out of aisc_validator.py. | AISC | CC | S | P2 | None |
| 3.5 | Bolting and welding cost levers as estimator guidance: two-bolt-size rule with a 1/4-inch diameter gap, slip-critical only where the EOR demands it, the 5/16-inch one-pass fillet threshold (cost scales with passes, not leg size), CJP as the most expensive weld. | AISC | CC | S | P2 | None |

## Workstream 4 - AI workflow and platform

| ID | Action | Source | Owner | Effort | Priority | Decision gate |
|----|--------|--------|-------|--------|----------|---------------|
| 4.1 | Enrich project-indexer and drawing-analyzer outputs with cross_references.json and coordination_issues.json, matching the durable-index pattern. Keep "AI classifies, scripts never pattern-match." | ConstructIQ 7.2 | CC | M | P1 | None |
| 4.2 | Distribute skills/ as a GitHub-backed "YourCo-OS" plugin marketplace so Owner and Joseph pull synced, version-controlled skills without an EXE rebuild. | ConstructIQ 7.6 | Joseph + CC | M | P2 | Owner approves a private GitHub-backed marketplace |
| 4.3 | Reaffirm connector security: least privilege, no cost or rate data in cloud connectors, destructive or outbound actions need human confirmation. Add to the governance reference. | ConstructIQ 5 | CC | S | P1 | None |
| 4.4 | Confirm model tiering already matches (Haiku extract, Sonnet default, Opus hard work). No change expected. | ConstructIQ 4 | Joseph | S | P2 | None |

## Workstream 5 - Image generation tooling (marketing visuals only, Joseph-gated)

Applies to Your Company marketing and capability visuals only. It never touches client bid
renderings, which stay locked to the real S0.0 3D rendering doctrine. No AI image model
goes near a bid render.

| ID | Action | Source | Owner | Effort | Priority | Decision gate |
|----|--------|--------|-------|--------|----------|---------------|
| 5.1 | Test Ideogram 4 first for text-heavy marketing stills (capability one-pagers, social cards). Keep GPT Image 2 as the paid backstop when exact spelling must be guaranteed. | IMAGE-GEN | Joseph | S | P1 | Joseph confirms the Ideogram Open Model license permits commercial use before any deliverable. Budget $20/month Plus for private generation if the free tier public-generation limit is a problem |
| 5.2 | Try Cosmos 3 on the Hugging Face Space for industrial and mechanical imagery (Style 01). | IMAGE-GEN | Joseph | S | P2 | Joseph reads the NVIDIA Cosmos license and confirms whether our workstation GPU can run Cosmos Nano locally (needs a high-VRAM professional NVIDIA card, figure unverified). Cloud only until then |
| 5.3 | Any additive image-gen provider entry for Your Company goes in Video Creation/, confirmed against FOLDER_INSTRUCTIONS.md and CLAUDE.md. Do not change the locked bid-render doctrine. | IMAGE-GEN | CC + Joseph | S | P2 | None |
| 5.4 | Add a Whisper key to ~/.config/watch/.env (GROQ_API_KEY preferred, else OPENAI_API_KEY) so future caption-less /watch videos get a transcript instead of frames-only. | IMAGE-GEN, AISC captions note | Joseph | S | P1 | None |

## Workstream 6 - Training and knowledge distribution

| ID | Action | Source | Owner | Effort | Priority | Decision gate |
|----|--------|--------|-------|--------|----------|---------------|
| 6.1 | Distribute the 18-video AISC re-watch list to named people. Joseph and Ivan together: Connection Design as the Fabricator's Representative, Understanding the Code of Standard Practice. PE and Ivan: Moment Connections Part 1, Bracing Connections, Load Path and Transfer Forces, Vertical Bracing Connections. PE: Erection Engineering of Low-Rise Buildings. Paul and Mario: The Erector's Perspective. Paul: Fastener Fundamentals. Mario: Weld Details The Good The Bad and The Ugly. QC: Quality Control and Quality Assurance. Ivan, PE, crew: Got Stiffness Base Plates, Field Fixes 1 and 2. Ivan: Introduction to Seismic Connections, To 3 or Not To 3. Whole team: Steel Fabrication Virtual Tour. | AISC re-watch list | Joseph + Owner | S | P1 | None. Schedule the viewings |
| 6.2 | Link the KBs into the 02_Wiki brain (the Knowledge-Bases MOC already points at them) and reference this plan from it. | This review | CC or Cowork | S | P2 | None |

## Decisions that need Owner, Ivan, or Joseph before code starts

- Owner: approve the connection-steel itemization as the new pricing posture (1.1), set the dollar-threshold escalation table (1.6), approve a private GitHub-backed skills marketplace (4.2), and approve any image-model spend (5.1).
- Ivan: sign the connection-pricing method (1.1), the takeoff row schema (1.3), the anchor-callout linter rules (3.1), and the material-grade defaults (3.2). These touch how a tonnage and a price are built, so they need the Director of Engineering, consistent with the calibration ownership.
- Joseph: image-gen license verification and GPU check (5.1, 5.2), the Whisper key (5.4), and the marketplace infrastructure (4.2).

## Recommended first sprint (P0 only)

1. Build the reconciliation advisory gate (1.2). Lowest risk, immediate value, cannot change a number, validated by ConstructIQ's 75 percent coverage and 17-unpriced-item result.
2. Stand up the connection take-off pass and the drawing-completeness and connection-information gate (1.1, 2.6, 2.1, 2.3), with Ivan signing the method. This is where the bid-accuracy money is.
3. Adopt the row schema with method and confidence tiers and the assumption string (1.3).
4. Lock the anchor-rod rule and grade defaults into the validator path (3.1, 3.2).

P0 items are code plus an Ivan sign-off. Run them in Claude Code on feature/count-gap-sf-a1
behind the existing review gates, self test before and after any Bridge edit, vj scan before
any commit. Everything stays verify-do-not-generate. The validator and bid_rates.py remain
the only source of weight and rate.
