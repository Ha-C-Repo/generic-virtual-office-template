# How to Set Up Claude Cowork for Construction - Step-by-Step (fjodH7eGwg0)

- URL: https://www.youtube.com/watch?v=fjodH7eGwg0
- Uploader: Tim Fairley (channel "Tim Fairley"); community referenced on-screen as "Contractor OS" / "ConstructIQ"
- Duration: 19:12 (1152s) | Upload date: 2026-05-18 | Views at capture: 6,579
- Frame count analyzed: 96 frames (1 every 12s), 640x360 source upscaled to 1280px
- Transcript source: YouTube auto-captions (en), pulled from the VTT caption track (video stream itself 403'd in yt-dlp; recovered via the tv-client format 18 and frames extracted manually). 561 deduplicated timestamped caption lines.

Thesis: A three-layer Cowork setup - a connected business-context layer (Notion), a Cowork project bound to the on-disk project folder, and a per-project `0. AI Context` folder built by a `/project-indexer` skill - so Claude always has both "how our company works" and "what this job is" before it does any construction task.

## Chronological walkthrough (with t=MM:SS anchors)

- t=00:00 Hook: most people use "Claude Work" as a chatbot with file access; it drifts, burns usage, and answers inaccurately. Promises a setup "10x better." Frame 1 shows the Cowork home ("Let's knock something off your list") with a project sidebar full of real electrical/HV estimating tasks (Verify max demand against drawings, Create pricing schedule for HV/S, Clarify SPI/SP2/132kV scope).
- t=00:24 Core principle: every construction task needs two kinds of context - project context (drawings, contract, specs) and business context / data layer (estimating rates, standard commercial positions, company background).
- t=00:57 Different document types must be treated differently. A PDF drawing set is processed fundamentally differently from a contract or a Gantt chart; AI does not natively handle these well, so you build workflows per format. Frame 7 shows him in Bluebeam Revu with an 11-page plumbing drawing set.
- t=01:27 The system has three layers. Layer 1 = business context / data layer.
- t=01:44 Demos Layer 1 in Notion (online notes + good Claude MCP connector). Stores text data (business processes, standard contract positions) and databases (a cost library). Frames 36-60 page through the "Bradman Construction - Business Context" Notion page.
- t=02:07 Connecting Notion: Customize > Connectors > connect Notion to Claude; then any chat or Cowork project can read it. Example: a cost library so "prepare a conceptual estimate" can read from it.
- t=02:45 Layer 2 = the Cowork project. Many people use Cowork without projects; a project lets Claude manage your project context. Steps: Projects tab > New project > select the project folder > rename it ("Construction Project Example") > instruction "I want your help managing this construction project" > Create. Frames 15-18.
- t=03:33 To resume, go back to Projects tab and select the folder.
- t=03:36 Layer 3 = the project folder itself (contract, drawings, specs, subcontractors, variation register, RFI register). Frame 20 shows the Explorer layout.
- t=03:53 He always adds a `0. AI Context` folder: a text representation of every document plus a synthesis of all drawings.
- t=04:06 Built by running his **project indexer** skill on every new project. First run is token-heavy; afterwards queries hit the markdown rather than the PDF, "20 to 40 times less tokens."
- t=04:48 Indexer also produces a drawings summary/list, identifies cross-references between drawings, and splits the set into per-sheet PDFs each with a text representation and a lower-resolution image. Frame 26 shows the per-sheet JSON+PDF+PNG triplets.
- t=05:13 Says he has separate videos on the project-indexer process; links it in the "Contractor OS" community.
- t=05:35 Recap of three context layers. Business context could be Notion, Google Drive, or GitHub (GitHub has "cooler implications" with Claude Code).
- t=06:03 For specific tasks you must either explicitly prompt Claude where to get info, or bake it into repeatable workflows called skills. Claude won't know your Notion DB exists unless told.
- t=06:48 What belongs in business context: company background, who you are, typical clients/projects. Mental model: "what would you want your estimator to know before they do the task?"
- t=07:25 Unlike a human hire with 10 years of tacit knowledge, AI needs everything spelled out (it was trained on "everything," designed to do marketing through to code).
- t=08:19 Business-context contents demoed: standard contract positions (accepted/rejected clauses, e.g. only a 12-month defects liability period, never accept pay-when-paid); estimating principles (when doing a takeoff, only measure primary quantities, sanity-check them, derive secondary from a secondary-quantity/assembly database); typical profit margins and markup ranges; confidence tagging (high/medium/low on takeoffs); production-rate library.
- t=09:45 Decision rules: when AI may proceed vs when it must check with you. Voice/writing standards - biggest one: keep it concise ("Claude is incredibly verbose," returns a 10-page review longer than the contract).
- t=10:34 Business context stays live; the project gets live access. Key writing rules/standards get pulled into the `0.ai context` folder when you first run the indexer, landing in the `claude.md` file that Claude reads every task. Frame 30 shows an example claude.md described verbally (architecture of where info lives, operating rules: answer concisely, confirm before overriding/deleting).
- t=11:41 The business layer is a single source of truth that anyone using Claude (even outside Cowork) can pull from; Notion makes team sharing easy.
- t=12:08 Layer 2 detail: open Cowork in the project folder; turn memory on so Claude builds working memory across chats. Frame 18/72 show the Memory panel ("Ask Claude to remember something and it'll save it here").
- t=12:38 Run the project indexer. It creates `claude.md` (overall instructions for every chat), `project.md` (project snapshot: contract, payment terms, structured summary), `memory.md` (an addition to Claude memory; a skill can summarize each chat into it), and `drawings.md` (high-level overview of all drawings and what to find in each). Frames 65-68 show all five files plus a `drawings` subfolder.
- t=13:45 Prompting Cowork differs from normal chat: be explicit about where to find information. Example typed in Frame 72: "using my cost library in notion / please prepare a conceptual estimate for this project."
- t=14:34 Bad prompt: "review the contract." Good prompt: "review the contract against my standard terms in Notion." Claude may have 3-4 connectors, so always state the source. Frame 75 shows that task running, referencing Instructions - CLAUDE.md.
- t=15:00 Or pre-build the source into a skill. He has many pre-built skills for construction-management tasks; example: an O&M-manual skill with explicit instructions on what info to get, where to get it, ask-the-user fallback, and exact Word headings/output format.
- t=15:55 To build a skill: define input/context needed, the workflow/data transformation, and the output format.
- t=16:07 Scheduled tasks in Cowork: he doesn't use them much - the limitation is the computer must stay on/awake (Frame 80: "Scheduled tasks only run while your computer is awake," Keep-awake toggle; Daily brief / Weekly review presets). Frame 83: a daily-brief scheduled prompt (calendar + unread emails + attention items).
- t=16:38 Better to use Claude Code + GitHub for routines that run when your computer is off. Says he has a separate "Claude routines" video.
- t=17:00 The real power: connect all your software via Claude connectors. Frames 13/90 show his connector list: Airtable, Canva, GitHub Integration, Gmail, Google Drive, Notion, Operum (CUSTOM), Smartsheet, VidIQ (CUSTOM), plus Google Calendar. Recommends Notion (business context), Google Drive, GitHub, Google Calendar. Outlook users swap Google Drive for SharePoint, Gmail for Outlook.
- t=17:57 Guardrails: in `claude.md`, specify when it can act vs when it must ask permission, and require approval before deleting.
- t=18:13 Token usage / model tiering: don't use Opus for easy tasks - use Sonnet for everyday work, Haiku for simple extraction (e.g. pulling info from drawings). Opus is most expensive. Frame 93 shows the picker: Opus 4.7 (most capable), Sonnet 4.6 (responsive everyday), Haiku 4.5 (fastest), plus an "Adaptive thinking" toggle.
- t=18:54 For real autonomy/automations, shift from Cowork to Claude Code, and use GitHub to integrate it. Frame 96 shows his Claude Code surface with GitHub Sessions and Pull requests ("Add weekly-progress-report skill," "Optimize batch operations and add database indexes").

## On-screen tools and Claude skills (names exactly as shown)

| Item | Type | Where shown | Notes |
|---|---|---|---|
| `project indexer` / `/project-indexer` | Skill (slash command) | Frames 22, 24, 28; t=04:06 | Builds the `0. AI Context` folder; per-sheet split; cross-reference detection |
| `Contractor os skills` | Personal plugin (skill pack) | Frames 13, 86, 90 | Active plugin holding his construction skills |
| `Pacific buildi...`, `Finance`, `Productivity` | Personal plugins | Frame 86 | All shown "Disabled" |
| Notion | Connector (MCP) | Frames 13, 90 | Read-only tools (5) "Always allow"; Write/delete tools (9) "Needs approval" |
| Airtable, Canva, GitHub Integration, Gmail, Google Drive, Smartsheet, Google Calendar | Connectors | Frames 13, 90 | Standard web connectors |
| Operum (CUSTOM), VidIQ (CUSTOM) | Custom connectors | Frames 13, 90 | "Operum HQ" also appears as a Notion teamspace; his production-rate library "maintained in detail in Operum" |
| Bluebeam Revu | External desktop app | Frame 7 | Used for drawing markup/takeoff, not part of Cowork |
| Notion page "Bradman Construction - Business Context" | Business-context doc | Frames 36-60 | The Layer-1 source of truth |
| Cowork project "Construction Project Example" | Cowork project | Frames 18-93 | Bound to on-disk "Construction Project" folder |
| Models: Opus 4.7, Sonnet 4.6, Haiku 4.5 + Adaptive thinking | Model picker | Frame 93 | His tiering advice maps to these |

Note on naming: the product is shown and labeled "Cowork" throughout the UI; the auto-caption transcribes it inconsistently as "Claude Work," "co-work," and "CoWork." Treat all three as the same product.

## The workflow, step by step (reproducible how-to)

1. Build Layer 1 (business context) in a connected store. He uses a single Notion page, "<Company> - Business Context," declared as "the source of truth for how <Company> does construction. Claude reads this when running any project-level workflow. Update once, every future project inherits the update." Sections seen: (1) Standard Contract Positions, (2) Estimating Principles, (3) Production Rate Library extract, (4) Resource rates, (5) Decision Rules, (6) Voice & Writing Standards.
2. Connect that store to Claude: Customize > Connectors > Notion > set tool permissions (read-only = Always allow; write/delete = Needs approval). Frame 90.
3. Create the Cowork project: Cowork > Projects > New project > pick the on-disk project folder > rename > add the instruction "I want your help managing this construction project" > Create. Turn Memory on. Frames 15-18.
4. Lay out the on-disk project folder with numbered top-level folders, e.g.: `0. AI Context`, `01_Contract`, `02_Drawings`, `03_Specifications`, `04_Subcontract_Returns`, `05_Correspondence`, `06_RFI_Register`, `07_Variations_Register`, `08_Programme`. Frame 20.
5. Run the indexer: type `/project-indexer` in the project. It generates `0. AI Context/` containing `claude.md`, `project.md`, `drawings.md`, `memory.md`, a `_DEMO_README.md`, and a `drawings/` subfolder; it also splits the drawing set into one PDF + PNG + JSON per sheet and records cross-references. Frames 22-68.
6. Prompt with explicit sources, e.g. "using my cost library in Notion, please prepare a conceptual estimate," or "review the contract against my standard terms in Notion." Or bake the source into a skill. Frames 72-75.
7. Pick the model per task cost: Haiku for extraction, Sonnet for everyday, Opus only for ambitious work. Frame 93.
8. For automations that must run unattended, move to Claude Code + GitHub rather than Cowork scheduled tasks. Frames 80, 96.

## What works / what does NOT (trust boundaries)

- Trusts AI for: text synthesis (the indexer's markdown summaries), drawing-set cross-referencing and summarization, conceptual estimates *driven from his own rate library*, contract review *against his own stated positions*, and routine correspondence.
- Refuses / constrains AI on: anything outside the explicitly stored positions. His Notion "Decision Rules" (Frame 50) hard-gate the AI: escalate to the director for any contract amendment outside the listed positions, any variation > $50,000 (or pending exposure > $100,000), any EOT/programme slip > 10 days, any subcontractor default, any correspondence using "claim/breach/termination"; act without asking only for variations < $10,000 and standard RFIs; ask for anything $10k-$50k.
- Estimating discipline (Frame 50/55, t=08:59): "Primary quantities measured directly... Secondary quantities derived via ratios, never re-measured. Cost = quantity x rate at the constraint resource. Always." Confidence tagging on every line item (High = quoted from sub or measured from issued-for-construction drawing; Medium = derived from rate x measured qty or comparable past project; Low = ballpark from cost-library median, requires verification). "Submissions with >15% low-confidence content require senior review."
- Guardrails in `claude.md`: confirm before overriding/deleting; require approval before destructive actions.
- He is explicitly skeptical of Cowork scheduled tasks (computer-must-be-on limitation) and routes real autonomy to Claude Code.

## Concrete numbers, rates, file names, examples shown

- Token reduction after indexing: "20 to 40 times less tokens" (t=04:33).
- `0. AI Context` folder size in demo: 34.9 KB (Frame 20 tooltip).
- Files in `0. AI Context`: `_DEMO_README.md`, `claude.md`, `drawings.md`, `memory.md`, `project.md`, and a `drawings/` subfolder (Frames 65-68).
- Drawing set example filename: `403183205-D-3-2-Structural-Dwgs-T2-25-No-pdf`, split into per-sheet JSON (33-128 KB) + PDF (267 KB-5,043 KB) + PNG (431 KB-2,209 KB) (Frame 26).
- Business-context figures (Frames 36-60, ConstructIQ's fictional "Bradman Construction," AS 4902 / Australian context):
  - Liquidated damages cap $2,500/day; Payment terms 14 days from claim (reject 30+); Defects liability 12 months standard (reject > 18 months unless paid); Public liability cap $20M unless project value justifies $50M.
  - Markup targets: Commercial fitout 12% (min 9%); Refurbishment/live environment 15% (min 12%); New build commercial 8% (min 6%); Civil/infrastructure 10% (min 7%); with risk premiums (+2% if novated design, +3% if occupied building, +2% if D&C, +3% if latent-conditions risk retained).
  - Resource rates extract: Site office hire $1,800; Skip and waste $2,400; Temporary power $850; Site amenity $1,200; Insurance allocation 0.8% of contract.
  - Voice: "Direct and practical. Get to the point. No corporate jargon. No 'leverage', 'utilise', 'robust', 'comprehensive', 'streamline', 'optimize'. Australian English always."
- Models shown: Opus 4.7, Sonnet 4.6, Haiku 4.5 (Frame 93).
- Prompt examples: "using my cost library in notion / please prepare a conceptual estimate for this project"; "review the contract against my standard terms in notion"; "Set up a scheduled task that gives me a morning brief each weekday: what's on my calendar, important unread emails, and anything that needs my attention today."

## Applicability to a structural steel fabricator (Your Company)

This video is almost a mirror of Your Company's existing architecture, which is reassuring and gives a few concrete adjustments. What transfers directly:

- The three-layer model is exactly Your Company's split. His "business context layer" = our governance/data layer (`CLAUDE.md`, `rates-and-pricing.md`, `bid_rates.py`, `owner-rules.md`, `company-details.md`, the precedent/supplier lists). His "project context" = our per-bid `0.ai-context/`. We already enforce "verify, don't generate," confidence tagging (high/med/low), and "SF is the controlling input, source it." He arrived at the same primary/secondary-quantity discipline ("measure primary, derive secondary by ratio") that our CLAUDE.md states as "the accuracy jump from ROM to bid-grade is a measured member takeoff, not SF x psf."
- The `0. AI Context` folder with `claude.md` / `project.md` / `drawings.md` / `memory.md` is essentially identical to our `0.ai-context/CLAUDE.md` loader template plus `project-indexer`/`drawing-analyzer` skills. We already ship a `project-indexer` skill that produces `0.ai-context` with `CLAUDE.md`, `project.md`, `drawings.md`, `memory.md` - so his pattern validates ours nearly file-for-file. Worth confirming our indexer also emits a per-sheet split (PDF + image + text/JSON per sheet) and a cross-reference index, which our `drawing-analyzer` already does.
- The "single source of truth, update once, every project inherits" framing is a clean way to describe our governance layer and is worth adopting verbatim in onboarding docs.
- Decision-rules table (when to act / when to ask / when to escalate, with dollar thresholds) is a tidy pattern we could formalize beyond our current Tier 1/2/3 governance - a concrete $-threshold escalation table for Owner would sharpen "ask before guessing."
- Model tiering advice matches our `data/model_routing.json` exactly (Haiku for extraction, Sonnet default, Opus only for hard reasoning). No change needed; it confirms our tier discipline.
- Connectors framing (read-only = always allow, write/delete = needs approval) is the right default and matches our "destructive or outbound actions need human confirmation" rule.

What does NOT transfer / needs care:

- He stores business context in Notion via the Notion MCP connector and recommends GitHub/Google Drive. Your Company's data is local files + SQLite (`data/*.db`, `bid_rates.py`) inside a desktop app, and CLAUDE.local.md marks `data/*.db` and `API Keys/` as do-not-touch. Putting CEO-locked rates or MATERIAL_COSTS into a cloud Notion/Drive connector would conflict with Hard Rule 4 (suppliers/costs internal only) and the API-keys secrecy rule. Keep the business layer local; do not lift his cloud-connector recommendation wholesale.
- His estimating is generic civil/fitout/electrical (AS 4902, Australian, $/day rates, no steel takeoff). Our controlling input is a measured AISC member takeoff through `bridge/aisc_validator.py`, not his $/SF or rate-x-quantity shortcut. His "secondary quantities derived via ratios" is fine for his trades but for us secondary steel still routes through validated weights, not pure ratios - our existing rule stands.
- He uses Bluebeam Revu for markup; we use PyMuPDF + our own `drawing-analyzer`. No adoption needed.
- Cowork scheduled tasks need the computer awake; he routes routines to Claude Code + GitHub. For us that maps to our `claude-routines-construction.md` and the existing async/background-thread patterns rather than Cowork scheduling. Our VJ-scan async pattern already covers unattended-style runs; cloud GitHub routines are out of scope for a signed desktop EXE shipped to Owner.
- His "no em-dash / no jargon / concise" voice rules are the same spirit as our Output Format Rules; nothing to import, but it confirms ours.

Net: nearly everything conceptual transfers and validates our current setup; the one thing to explicitly NOT copy is his cloud-Notion business-context store for cost/rate data, which would breach our Tier 1 supplier/cost confidentiality. The one worth borrowing is his explicit dollar-threshold decision-rules table.

## Caveats

- The video stream returned HTTP 403 in the standard watch pipeline (no JS runtime / no impersonation target for the default format `398+251`). Recovered by re-downloading with the tv player client at format 18 (640x360) and extracting frames manually, so frame resolution is modest (text in small Notion tables is legible but near the limit; figures above were read carefully but small numerals e.g. some markup percentages could be off by a digit).
- Frame sampling is 1 per 12s (96 frames over 19:12). UI transitions between sampled frames (e.g. the exact New-Project modal fields in Frame 16, which was mid-animation and blurred) were inferred from adjacent frames plus the transcript, not read field-by-field.
- Transcript is YouTube auto-captions, so product name ("Cowork" vs "Claude Work") and a few words (e.g. "debauchery register" almost certainly "defects-liability register" at t=08:50, "O 0.ai" = "0.ai") are caption artifacts, noted inline where load-bearing.
- "Bradman Construction," "Operum," and the dollar figures are ConstructIQ's demo/training data, not real Your Company figures.
