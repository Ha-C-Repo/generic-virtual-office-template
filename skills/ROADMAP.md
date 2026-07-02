# Skills Roadmap — v3.2.7 → v3.3

This is the queue of skill .md files identified during the v3.2.7
sandbox audit. Ordered by impact (frequency × pain × ease).

Three have already shipped in v3.2.7:
- `skills/vj-self-knowledge/SKILL.md` — VJ becomes an expert in the codebase
- `skills/owner-voice-check/SKILL.md` — final voice gate
- `skills/bid-output-scrubber/SKILL.md` — six bid-content rules in one pass

## Tier 1 — Next sprint (highest ROI)

### emr-letter-drafter
**Why:** the Owner's #1 blocker per his profile. EMR letter from Texas
Mutual (800-859-5995, Policy [POLICY NUMBER]) unblocks Marathon Petroleum
approval. This is single-greatest-leverage skill possible right now.
**Function:** Drafts the request letter/email to Texas Mutual, tracks
the request status, and surfaces the blocker in `morning_briefing`
output until resolved.

### marathon-prequal-tracker
**Why:** Marathon Petroleum is the named target client. The
prequalification has multiple parallel blockers (EMR letter, ISN
RAVS, $2M Auto Liability CSL, ISN 400). Today they're tracked as
separate items in `compliance_summary`. A skill that aggregates the
Marathon-specific state and shows the critical path saves Owner
from cross-referencing across screens.
**Function:** Pulls all Marathon-related blockers, shows the order
they need to clear, surfaces the next one when the prior one resolves.

### bid-pricing-sanity-check
**Why:** Catches arithmetic drift before a bid ships. Validates a
generated bid against the rates table: fab $3,750/ton @ 31% GP,
erection $970/ton @ 30%, joists $4,500/ton @ 40%, deck $[ROOF DECK RATE]/SF @
23%, anchor rods $[ANCHOR RATE]/EA @ 31%. Flags any rate that diverges by
more than 3% without an explicit note.
**Function:** Reads the generated bid, computes effective rate per
line, compares to baseline, surfaces deviations.

### takeoff-completeness-check
**Why:** Bids that miss a CSI section get returned. Verifies a
takeoff covers all standard sections: 05 05 13, 05 12 00, 05 21 00,
05 31 00, 05 50 00, 05 51 00, Shop Drawings. Per the Owner's bid
format standard (rule 2.5), missing sections must be listed as N/A
rather than omitted.
**Function:** Reads the takeoff data, checks for all six sections,
adds missing ones as N/A rows, surfaces what was added.

### two-pdf-pair-check
**Why:** Per the Owner's standing rule, every bid is TWO PDFs (client
proposal + GP report with `-GP` suffix). Single-PDF deliveries are
incomplete. This skill enforces the pairing.
**Function:** After a proposal PDF is saved, verify the matching
`-GP` PDF exists in the same folder. If missing, auto-trigger
generation. If generation fails, block delivery and surface.

## Tier 2 — Sprint after next

### isn-ravs-responder
**Why:** Already a system-prompt feature ("Answer ISNetworld RAVS
questionnaires using the 18 safety programs on file"). Currently
ad-hoc. Making it a skill formalizes the mapping.
**Function:** Maps the 18 safety programs to typical ISN questions,
generates draft responses, flags questions that need Paul Guerrero's
input.

### scope-creep-detector
**Why:** Already a system-prompt feature. Currently runs only when
Owner explicitly asks "detect scope creep in this email." A skill
that triggers on inbound email scans would catch CO opportunities
Owner misses.
**Function:** Pattern-matches inbound emails for additive language
("can you also..." "we'd like to add..." "while you're at it..."),
drafts a G701 if confirmed.

### supplier-quote-tracker
**Why:** Rule 3.3: anchor bolts above $10K need three supplier
quotes. Today nothing tracks whether the three quotes were obtained.
**Function:** When a bid lists anchor bolts > $10K, requires three
quote records before the bid can be marked "ready to send."

### drawing-stage-classifier
**Why:** Pricing contingency depends on drawing stage (schematic vs
DD vs 50% CD vs 90% CD vs 100% CD vs approved-for-construction).
Today this is captured in the bid header but not enforced anywhere.
**Function:** Reads the drawing set, classifies the stage from
title-block markings (or asks if ambiguous), applies the appropriate
contingency adder.

## Tier 3 — Concept-level, defer

### connection-standardization (Gemini suggested)
Engineering-domain. EORs sign drawings. Reframe as an RFI suggestion
skill, not auto-substitution.

### structural-friction-RFI (Gemini suggested)
K-Zone clearance is real but the trigger frequency is low. Build
when the first violation is detected manually, not preemptively.

### carbon-intelligence / Green Steel ESG (Gemini suggested)
Wrong target market. Marathon, Bechtel, Fluor, Kiewit buy on EMR
and ISN. Reconsider if Your Company pursues public-works contracts
where ESG matters.

### MCP Procore/Bluebeam integration (Gemini suggested)
Real value but PAID. Procore $25-50/user/month, Bluebeam ~$240/year.
Decision for Owner when GC integration becomes a bottleneck.

### 3-tier intelligent routing (Gemini suggested, reframed)
Implement as a routing skill that documents the existing tier
behavior, not as a new framework. Tier 1 = local Python (already),
Tier 2 = Gemini Flash for triage (already configured), Tier 3 =
Claude/GPT-4o for reasoning (current default). Document the rules,
don't rebuild the system.

## Update protocol

When a Tier 1 skill ships:
1. Move it out of this roadmap
2. Add it to `skills/INDEX.md` (or equivalent)
3. Document its trigger patterns in the main router prompt
4. Add a row to CHANGELOG.md with the version it shipped in
5. Re-prioritize remaining Tier 1 items if reality showed a
   higher-leverage skill mid-sprint

## External references

- Reference: shanraisshan/claude-code-best-practice (MIT) - community Claude Code feature tracker, checked 2026-06-10. Added per _handoff/SOCIAL-CAPTURE-INTEGRATION-PLAN-2026-06-10.md, approved by Owner 2026-06-10.

## Skill training method (D4)
When building any new skill, feed it about 5 historical input/output pairs from completed jobs before first use, then test on one fresh input it has not seen. Completed bids and the ACP award are the pair source. A skill that has not passed a fresh-input test is marked DRAFT in its description.
