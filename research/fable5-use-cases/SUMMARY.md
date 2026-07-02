# Claude Fable 5 Use Cases (RoboNuggets) - Summary

Source: one YouTube video, "Claude Fable 5 Use Cases You MUST Try Now" by Jay E / RoboNuggets (11:14, uploaded 2026-07-02), watched 2026-07-02 at full depth (download, two 1024px frame windows of 100 frames each read in parallel, complete caption transcript). Per-video report beside this file: `_WXtkSvIDJs.md`. Lens: what could improve Your Company's systems.

This is a general Claude-model tips/marketing video, not construction content. Most of the runtime is hype (X screenshots, a product tour, a paid-community upsell). The transferable substance is the copy-paste prompts from an on-screen guide PDF, captured verbatim in the per-video report. It does not map to any existing `docs/*-KB.md`; its internal touchpoints are the CLAUDE.md "AI Model Routing" section (`bridge/direct_route.py`) and the self-repair / `vj scan` governance layer.

## What transfers to Your Company (prioritized)

1. **A periodic READ-ONLY "workspace / context audit" (HIGH).** The video's best artifact is a six-area audit prompt: score always-loaded memory (delete-test every CLAUDE.md rule; is it over ~200 lines?), stale pointers (every referenced path that no longer exists), duplicates/conflicts across always-loaded files, unused/overlapping/over-prescriptive skills, unused MCP servers (and MCP servers duplicating a CLI), and safety (plaintext secrets, must-always rules that should be hooks). Deliver a scorecard, the top 10 fixes, and exact edits for the top 3, "citing file:line, no guessed findings, report first, change nothing until approved." This maps one-to-one onto Your Company's sprawling governance layer (CLAUDE.md + 0.ai-context + owner-rules.md + ~10 skills + memory + loose planning docs). Adapt it as a `vj scan` / `SelfRepairEngine` category. Proof it would pay off: CLAUDE.md cites `data/model_routing.json` as the routing config, but that file does not exist in the repo (only `bridge/direct_route.py` does) - a live stale pointer of exactly the kind the audit catches. Guardrails: advisory only, human-approved, back up before overwriting, use `safe_write.py` for CLAUDE.md.
2. **"Plan on the top tier, execute on cheaper tiers" (MEDIUM-HIGH).** A community pattern shown on screen ("Fable plans, cheaper models execute"), reinforced by the on-screen fact that Fable 5 "draws down usage much faster than Opus 4.8." This is our existing tier discipline ("Sonnet by default, Opus only for hard reasoning, do not auto-escalate") stated as a workflow: reserve the most expensive model for planning/skill-writing, let cheaper models do the bulk work. Relevant to `data/model_routing.json` if/when it is created.
3. **`/loop` self-scoring for DESIGN output only (MEDIUM).** "Treat the previous iteration as 100, this pass must reach 120, keep changes only if obviously better, log each pass" - a legitimate iterative-polish loop for renders, proposal/GP layout, brand visuals, and Video Creation output. Hard boundary: visuals only, never bid numbers, tonnage, or rates (those stay deterministic via `aisc_validator.py` / `bid_rates.py`).
4. **Render dense output to an interactive HTML artifact / designed PDF for review (MEDIUM).** Instead of dumping prose in chat, build a laid-out artifact for reviewing a takeoff reconciliation, a coverage report, or an audit scorecard.
5. **Cost-gate + critic-subagent for the paid render/video pipeline (MEDIUM).** "Before any paid generation, quote model, quantity, and rough cost, then wait for go," plus a critic subagent that blocks weak output before it reaches the human (our `VirtualOwner` gate applied to generated content).

Also worth borrowing: the guide's prompt-design principles - interview first (ask before guessing), give the reason not only the request, act don't overplan, verify before claiming done ("only claim what you actually verified"), and cost gates. These already echo our operating rules; the one difference is they batch 3+ clarifying questions while our rule is one question per turn - adopt the intent within our constraint.

## Reject or guard

- All capability and pricing claims (Stripe 50M-line migration in a day, "90-95%," "beats Sonnet/Opus," the July 7 usage-pricing date) are unverified marketing; LOW confidence, keep out of any priced output. Verify Fable 5 cost/availability via the `claude-api` skill.
- The strategy-report numbers are fictional sample data (a made-up "Ridgeline Plumbing Co."), not a benchmark.
- Third-party connectors (Higgsfield, fal.ai) and models (GPT Image 2, Seedance, Krea) need a Dependency-tax review; the Video Creation studio already uses gpt-image-1 and Gemini. Tier 1 brand rules and the studio firewall still apply.
- The lead-gen / cold-postcard and 3D-games/real-estate use cases are out of scope for steel-fab bidding.

## Video index

| Video ID | Title | Duration | One-line takeaway | Report |
|---|---|---|---|---|
| _WXtkSvIDJs | Claude Fable 5 Use Cases You MUST Try Now | 11:14 | Mostly hype; the reusable artifact is a six-area agentic-workspace audit prompt (stale pointers, duplicate/conflicting rules, unused skills) plus a "plan on the top tier, execute on cheaper tiers" routing pattern and a /loop design self-scoring technique | _WXtkSvIDJs.md |

## Caveats

- Transcript is complete and reliable (captions, 342 segments). On-screen prompts, model selector, and audit-output format were read from 200 frames at 1024px and are reliable transcriptions; the underlying claims are the presenter's own and unverified by us.
- No supplier names, AISC weights, tonnages, or rates appear or were introduced. Nothing here changes `aisc_validator.py` or `bid_rates.py`.
- The guide PDF, community, and external links were not downloaded or followed.
