# Claude Fable 5 Use Cases You MUST Try Now (_WXtkSvIDJs)

- **URL:** https://www.youtube.com/watch?v=_WXtkSvIDJs
- **Uploader:** Jay E | RoboNuggets
- **Duration:** 11:14 (673.7s)
- **Frames analyzed:** 200 (two 1024px windows of 100 frames each, ~3.4s spacing; two parallel reader agents)
- **Transcript source:** captions (342 segments, complete)
- **Watched:** 2026-07-02 (via /watch)
- **What it is:** an AI-tips / model-hype video from the RoboNuggets channel, walking through five general use cases for Claude Fable 5 (`claude-fable-5`, the flagship of the Claude 5 family). NOT construction-specific, and the video runtime is mostly marketing (X screenshots, a product tour, a paid-community upsell, pixel-font slides). The real substance is a downloadable guide PDF, "Claude Fable 5 EXTREME use cases," whose copy-paste prompts were fully legible on screen and are captured verbatim below. Three of those prompts, plus one routing pattern, transfer usefully to Your Company.
- **Maps to an existing docs/ KB?** No. Closest internal touchpoints: the "AI Model Routing" section of CLAUDE.md (and `bridge/direct_route.py`), and the self-repair / `vj scan` governance layer. No `docs/*-KB.md` covers model use-cases or workspace tooling.

## Framing (and why to discount most of it)

Urgency marketing throughout: Fable 5 is "the world's most powerful AI model," free on the normal subscription for about a week before usage-based pricing "makes it much more expensive" (he says available "up until the 7th of July... at least from what Anthropic is telling us"). He claims he used Fable 5 to run a "last 30 days research project on itself" across YouTube, X, and Reddit. An on-screen infographic frames it as "96 items pulled, 803K YouTube views, 217K X likes, 16.6K Reddit upvotes, 5 sources," and claims the model "launched June 9, got pulled by US export controls June 12, came back worldwide July 1." Every capability and pricing claim in the video is an unverified third-party assertion. Per governance, treat all of it as LOW confidence; verify any Fable 5 cost/availability claim against Anthropic's own docs via the `claude-api` skill before acting.

## Model / cost facts shown on screen (reference for model routing; screenshots, so MED confidence)

- **Claude model selector (HIGH legibility, claude.ai):** Fable 5 - "Included until July 7 - For your toughest challenges"; Opus 4.8 - "For complex tasks"; Sonnet 5 - "Most efficient for everyday tasks"; Haiku 4.5 - "Fastest for quick answers." This confirms the Claude 5 family tiering our environment already documents.
- **Fable 5 usage tooltip (verbatim):** "You can use up to 50% of your weekly limits on Fable 5, then it runs on usage credits. Fable 5 draws down usage much faster than Opus 4.8." This is an Anthropic UI string, so more credible than the presenter's hype, but still a screenshot; confirm before relying on it. Directly relevant to a model-routing/cost decision: Fable 5 is the most expensive tier and should be reserved, not defaulted.

## The five use cases (as shown in the guide PDF), with verbatim prompts where captured

The guide numbers them 01 3D worlds, 02 Custom software, 03 Workspace audit, 04 Strategy session, 05 Content factory. The guide's stated design principles (its "How to use this guide" page): it interviews you first (3+ questions before building); give the reason, not only the request; aim high; act, don't overplan; verify before done; and cost gates (anything that spends money must quote model, quantity, and rough cost, and wait for your yes). Those six principles are the genuinely useful meta-lesson and largely echo our own operating rules.

### 01 - 3D explorable world (Three.js one-shot) + the /loop self-scoring upgrade

Not relevant as a product (games / real-estate smart maps), but two prompt clauses are reusable. The base prompt ends with: "Before you build, interview me - at least 3 quick questions in one batch... After that, act - don't give me options or a plan, give me the file. Before you report done, verify your own work: open the file, check the console for errors, and confirm every named area is reachable on foot. Only claim what you actually verified." The follow-up (verbatim, HIGH):

> /loop Improve the visuals of this 3D world. Treat the previous iteration as a 100 - this pass must land at 120 or better: richer geometry and detail, better lighting and materials, more atmosphere and life. Open the file, screenshot it, compare it side by side against the previous iteration, and keep the changes only if the improvement is obvious. Log what you improved each pass.

The reusable idea: for output whose quality is aesthetic and hard to verify objectively, score the prior pass as 100, require the next to reach 120, keep changes only if the improvement is obvious, and log each pass.

### 03 - Workspace audit "like a context engineer" (the single highest-value artifact)

Guide intro: "Memory files, skills, and MCP servers rot quietly: stale pointers, duplicate rules, context-eating servers. This audit is built from Anthropic's own guidance on memory, skills, and context engineering." Prompt (verbatim, HIGH):

> Audit my agentic workspace like a context engineer. You have full read access; change NOTHING yet - report first, then one batch of fixes after I approve.
>
> Before you audit, interview me - at least 3 questions in one batch so we're aligned on the outcome: what's been annoying me day to day, what's sacred and must not be touched, and how aggressive I want the cleanup to be.
>
> Score these six areas out of 10, citing the exact file and line for every finding:
>
> 1. Always-loaded memory: is my CLAUDE.md file over ~200 lines? Run the delete test on every rule - "would removing this cause mistakes?" - and flag the ones that fail. Flag detail that belongs in on-demand files instead of loading every turn.
> 2. Stale pointers: check EVERY file path referenced in CLAUDE.md, memory indexes, and skills. List each one pointing at a file that no longer exists - a stale pointer teaches you things that are no longer true.
> 3. Duplicates and conflicts: the same fact stated in two loaded files (a token tax on every turn), or two rules that contradict each other (you'd pick one arbitrarily).
> 4. Skills: vague descriptions that could misroute, skills that overlap the same trigger, skills never invoked, and skills so prescriptive they'd handcuff a newer model.
> 5. MCP servers and tools: servers unused in recent sessions that still cost context, and any MCP server duplicating a CLI I already have (CLIs are cheaper).
> 6. Safety: secrets sitting in plaintext anywhere in the workspace, must-always-happen rules living as prose instead of hooks, and the weak spots in my permission setup.
>
> If I have a graph or visualization skill (like /graphify), use it to map which files reference which - the orphans and dead links show up instantly on the map.
>
> Deliver: a scorecard per area, the top 10 fixes ranked by impact, and the exact edits for the top 3. Ground every claim in something you actually read this session - no guessed findings.

On screen it runs in an agent surface (Claude Code / a "ROBO" desktop agent) and first fires an `AskUserQuestion` tabbed interview (Pain points / Sacred / Aggression / Skill usage) before doing anything - a clean "ask before guessing" implementation. The demo output is worth noting as a format template: a "Stale pointers 7/10" table of `file:line -> points at -> reality` (all 9 dead links verified with an existence check that session); a "Duplicates and conflicts 4/10" section catching a rule stated three times and two rules that contradict each other (one file says `start chrome`, another says `start ""`); and a "Skills 5/10" census finding that 91 of 131 skills had zero mentions across the conversation logs (with the honest hedge "usage proxy, not proof - logs may miss some invocations").

### 02 - Build custom internal software (reusable prompt discipline)

Key transferable clauses (verbatim excerpts, HIGH): "I work as [role] and every week I lose hours to [the repetitive task - writing quotes, chasing invoices, formatting reports, scheduling]... build me custom software that makes this task nearly disappear... Start by interviewing me like a software consultant - at least 3 and up to 8 questions in one batch... build it: a local app (a single HTML file, or a small local server only if it genuinely needs one)... Don't add features beyond what the task requires - do the simplest thing that works well. Establish a way to check your own work as you build, and test the full workflow end to end with realistic sample data before you hand it over. When you report back, lead with what it does and only claim what you actually tested." The named example tasks ("writing quotes, chasing invoices, formatting reports, scheduling") map almost exactly to a fabricator's back office.

### 04 - Strategy session -> throwaway HTML + designed PDF (the render-to-HTML technique)

The prompt asks the model to read your goals/strategy notes, interview you 3+ questions, then "Build me an HTML strategy session: a single file with 10 sharp questions... Wire in a 'Generate report' button that works fully offline: score my answers by area, name my weakest area... give me this week's 3 moves ranked by impact... Verify the file actually works before handing it over." The demo produced a running HTML questionnaire and a designed 5-page PDF (scorecard, SWOT, top-3 actions with KPIs, a 90-day roadmap, a Today-vs-Day-90 KPI table). All figures in that report are from a fictional sample client ("Ridgeline Plumbing Co."), not real data. The transferable technique is "render dense output as an interactive HTML artifact / designed PDF for review instead of dumping prose in chat."

### 05 - Content factory (cost-gate + critic-subagent pattern)

The prompt runs a "council of subagents - a writer, an art director, and a critic that blocks anything weak before it reaches you," and bakes in two gates worth stealing (verbatim): "If neither [MCP] is connected, stop and tell me what to enable first" and "Before ANY paid generation, quote the model, quantity, and rough cost, then wait for my go." Callout: "The council is the secret: the critic subagent is what separates a factory from a spam cannon. Never remove it." Tools named: Higgsfield MCP (subscription) or fal.ai MCP (pay-per-generation), stills via "GPT Image 2," video via "Seedance 2.0"; fal.ai also surfaced Krea 2 Turbo and Flux Kontext.

### Two extra patterns from the "how people use Fable 5" infographic (community-sourced, LOW confidence)

- "Big one-shots: migrations, refactors, bug hunts" - claims Stripe finished a 50-million-line Ruby migration in one day and Node.js core rewrote WHATWG Streams in C++. Unverified, but the category (use the top tier for a large one-shot refactor or bug hunt) is real.
- "Fable plans, cheaper models execute" - "Fable writes the plan and the skills, then Opus 4.8 / Sonnet 5 / Codex do the typing"; a cited thread: "have Fable 5 write skills NOW to tell Opus 4.8 how to think." This is a concrete routing pattern (plan on the expensive tier, execute on cheaper tiers).

## What actually transfers to Your Company (prioritized)

1. **A periodic "workspace / context audit," READ-ONLY and advisory (HIGH).** Use case 03 is the strongest transfer and is close to plug-and-play. Your Company's governance/context layer is large and visibly sprawling (`CLAUDE.md`, `0.ai-context/CLAUDE.md`, `INDEX.md`, `owner-rules.md`, `brand-voice.md`, `company-details.md`, ~10 skills, the memory system, plus many loose planning/handoff `.md` files and backup folders in the working tree). Adapt the six-area audit as a `vj scan`/`SelfRepairEngine` category that scores the context layer and flags: (a) stale pointers - every path referenced in CLAUDE.md, INDEX.md, memory indexes, and skills that no longer exists; (b) duplicate or conflicting rules across CLAUDE.md vs 0.ai-context/CLAUDE.md vs owner-rules.md; (c) skills that never trigger; (d) MCP servers duplicating a CLI we already have. Concrete proof it would pay off, found while writing this note: CLAUDE.md's AI Model Routing section says "Config in `data/model_routing.json`," but that file does not exist anywhere in the repo (only `bridge/direct_route.py` is present) - a live stale pointer of exactly the kind area 2 catches. The audit's own framing ("report first, change nothing, one approved batch, cite file:line, no guessed findings") is already our governance posture: advisory, human-approved, back up before overwriting, and use `safe_write.py` for CLAUDE.md. The "what's sacred / how aggressive" gating maps to our Tier 1/2/3 discipline.
2. **"Plan on the top tier, execute on cheaper tiers" routing discipline (MEDIUM-HIGH).** The infographic's use case 02 is our existing tier rule ("Sonnet by default. Opus only for genuinely hard reasoning... Do not auto-escalate to the highest tier") stated as a workflow: reserve the most expensive model (Fable 5 / Opus) to write the plan or the skill, then let cheaper models execute. Combined with the on-screen fact that Fable 5 "draws down usage much faster than Opus 4.8," the lesson for `data/model_routing.json` (once it exists) is to keep the top tier for planning/hard-reasoning steps only, never for bulk execution.
3. **The `/loop` "100 -> 120, keep only if obviously better, log each pass" self-scoring loop, for DESIGN output only (MEDIUM).** For aesthetic deliverables that are hard to verify - page-1 proposal renders, proposal/GP-report layout, brand visuals, Video Creation studio output - an iterative-polish loop is legitimate. Hard boundary: visuals and formatting only. It must never touch a bid number, tonnage, quantity, or rate; those are verified deterministically (AISC via `bridge/aisc_validator.py`, rates via `bridge/bid_rates.py`), never "self-scored better." A self-improvement loop over numbers would be a direct verify-do-not-generate violation.
4. **Render dense output to an interactive HTML artifact / designed PDF for review (MEDIUM).** Use case 04's "throwaway HTML" idea fits reviewing a takeoff reconciliation, a bid-vs-requirements coverage report, an audit scorecard, or a GP comparison. We already generate HTML/PDF; the nudge is to default complex review output to a laid-out artifact rather than chat prose. Keep Tier 1 rules on any client-facing surface (no supplier names, no margin data).
5. **Cost-gate + critic-subagent for the render/video pipeline (MEDIUM).** Use case 05's "before any paid generation, quote model, quantity, and rough cost, then wait for go" is a clean approval gate for our paid image generation (gpt-image-1) and any video generation. The "critic subagent that blocks weak output before it reaches the human" is essentially our `VirtualOwner` review-rules gate applied to generated content.

## Lower-value or non-transferable (honest accounting)

- **Custom internal software (use case 02):** the discipline (interview first, single HTML file, test with realistic data, "only claim what you actually tested," do the simplest thing) is sound and echoes our operating rules, but building internal tools is already what the Virtual Office app is. Low incremental value beyond adopting those prompt clauses.
- **The lead-gen / cold-postcard ad workflow:** a creative-agency growth play (watch the Meta ad library, scrape Google profiles, mail "before/after" postcards). Not core to steel-fab bidding; obvious data-hygiene and brand-rule risks; out of scope.
- **3D worlds / games / real-estate smart maps:** not applicable as a product. The only tangential link is our own estimate-grade 3D coordinate model and Tekla viewport work, which are engineering QC artifacts, not vibe-coded game worlds.
- **fal.ai / Higgsfield / GPT Image 2 / Seedance:** the only concrete tooling names for the Video Creation studio, which already uses gpt-image-1 and Gemini. Any such connector needs a Dependency-tax review and must respect the studio firewall and Tier 1 brand rules (no PEMB language, no brand blending, no supplier names). Pricing is unverified.

## Governance flags

- Every capability figure (the Stripe migration, "90-95% there," "beats Sonnet/Opus," "a month of campaign work in a day," the July 7 pricing date) is an unverified third-party claim. LOW confidence. None may inform a priced output.
- All numbers in the strategy-session demo (6-hour response, 38% win rate, 12% repeat revenue, etc.) are fictional sample data for "Ridgeline Plumbing Co." - not real, not a benchmark.
- No AISC weights, tonnages, or rates appear in this video; nothing here changes `aisc_validator.py` or `bid_rates.py`.
- No supplier names appear or are introduced. Third-party tools named (Higgsfield, fal.ai, GPT Image 2, Seedance, Krea) are external products, not Your Company suppliers; none should be adopted without a Dependency-tax review.
- One difference from our rules worth noting: the guide batches "3+ clarifying questions in one message," whereas our output rule is one clarifying question per turn. Adopt the intent (ask before guessing, align first) within our one-question-per-turn constraint.

## Caveats on this analysis

- Transcript is complete and reliable (captions, 342 segments). The five use cases and the framing are from the spoken track.
- The verbatim prompts, model selector, cost tooltip, and audit-output format were read from 200 frames at 1024px across two windows and were legible (HIGH); the underlying capability and pricing claims are the presenter's own and are unverified by us.
- I did not download the presenter's guide PDF, join the community, or follow any external link; the prompts above were transcribed from the on-screen renders.
