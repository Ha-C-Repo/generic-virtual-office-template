# Claude Plugins for Construction - Skills, Commands, Agents, MCPs and Hooks (iCNSq4FLboE)

- URL: https://www.youtube.com/watch?v=iCNSq4FLboE
- Uploader: Tim Fairley
- Duration: 11:17 (676.7s)
- Frame count: 80 frames @ 0.118 fps (sparse, full-mode; 512px wide)
- Transcript source: captions (318 segments)

Thesis: A plugin is the shippable, team-distributable container that bundles many skills plus connectors, sub-agents, and (in Claude Code) hooks, and the video walks through using/customizing the third-party "ContractorOS" construction plugin inside Claude Cowork and then publishing your own plugin from a GitHub repo so a whole company pulls one shared, version-controlled library of construction workflows.

## Chronological walkthrough (with t=MM:SS anchors)

- t=00:02 Framing: Claude is a generalist trained on the whole internet; to make it genuinely good at construction tasks you use plugins. Video promises to define a plugin, contrast it with a skill, and show install/setup.
- t=00:20 Definition of a skill: a pre-built, stored workflow inside Claude so a task (cash flow forecast, takeoff, contract admin) runs the same way every time, callable from chat instead of re-prompting.
- t=00:38 Live example: user types "review my contract using contract-review" (frame 6 shows the slash-style autocomplete: context, contract-review, construction-takeoff, contract-administrator). The skill encodes going to a Notion database, looking up standard contract terms, comparing them to the contract, and outputting a departures register.
- t=01:09 Why skills matter: without one you re-explain the process each time, get inconsistent formats, miss information. With a skill you define once, test, iterate, and get the exact output format repeatedly.
- t=01:46 Skill mental model: every skill = input information + data transformation + output format. Example given: contract says 45-day payment terms, your standard max is 30 days, transformation flags the gap and writes a proposed amendment into a departures register. To build one: collect many real examples, go back-and-forth with Claude, then tell Claude to "store this as a skill" and it lands in your skills library (frames 7-19 show the contract-review skill running: a "Used a skill" card, a "Contract details" upload form, contract-type selector with Main contract / Subcontract / Consultancy / Collateral warranty / Framework / Other, side selector Employer-client / Main contractor / Subcontractor / Consultant, and a contract-form selector NEC4 / JCT / FIDIC / AIA-ConsensusDocs / CCDC / AS-Australian / Bespoke).
- t=02:54 Limits of a bare skill: works for one person, one task, one computer. A construction company wants multiple people on the same skill, built-in connections to its data and software, and version control so a change to a standard contract position updates everyone. Skills also do not bundle (you cannot cleanly nest a contract-review skill inside a pre-construction workflow).
- t=03:44 Solution = a plugin. "A plugin is a combination of skills." It can also hold connectors to software tools, agents that perform long-running complex tasks, and (only in Claude Code) automated event handlers called hooks.
- t=04:11 Scope note: this video focuses on plugins inside Claude Cowork; Claude Code adds extra capability such as the automated event handlers (hooks).
- t=04:22 Two sources of plugins: build your own, or browse Anthropic's library. Anthropic ships finance, design, marketing, legal plugins. Each gives Claude specific capability (the finance plugin contains skills: audit support, financial statements, journal entries / journal entry prep, plus suggested connectors). Frame 33 shows the Anthropic & Partners Directory: Engineering, Data, Product management, Operations, Sales, Legal, Pdf viewer, Brand voice.
- t=04:57 Third-party example: the ContractorOS plugin, "a library of 30 specific construction management tasks" plus recommended connectors. Installing it is "like giving Claude a construction brain." A link is promised in the video description.
- t=05:17 After install you get every construction skill in the plugin: construction take-offs, contract reviews, departures registers, generating Gantt charts. Frame 30/41 plugin card reads: "ContractorOS skills bundle. 27 construction skills covering bidding, estimating, procurement, project controls, commercial, contract admin, and site management. Companion to contractor-os-setup." (Note the spoken "30" vs on-screen "27" mismatch; see Caveats.)
- t=05:34 Customizing a plugin: open the plugin and ask Claude to customize it. Demo (frames 42-57): user prompt "Customize the 'contractor-os-skills' plugin for me based on my company / i want to customize this to pull data from my business context and construction rate library in notion / here is the link for my notion databases https://www.notion.so/Bradman-Construction-Business-Context-...". Cowork spins up a skill named cowork-plugin-customizer, runs commands (Read plugin.json, Finding files, "Fetch Notion entities", "Loading tools"), and adds a Notion connector to the plugin's Context. (A transient "This isn't working right now. You can try again later" banner appears, frames 48-60.)
- t=06:06 Connector options called out: Notion is just an example; could be QuickBooks, Airtable, Google Drive / Google Workspace, Microsoft SharePoint - anything with a Claude connector. Frame 35 Connectors panel lists Snowflake, Databricks, Google Cloud BigQuery, Slack, Microsoft 365, Google Calendar, Gmail.
- t=06:35 Sub-agents for skills: a way to manage context bloat. Example: set up a construction project, then run the project-indexer skill as a separate spun-up agent so multiple agents run in parallel, faster, without overwhelming the context window; each has a specific focus. Claude runs quicker and more accurately.
- t=07:11 Orchestrator skills that run multiple sub-skills. Example: an "estimating workflow orchestrator" that calls four sub-skills. Frames 54-57 show the on-screen "Construction Estimating Workflow" skill, "Orchestrate the full tender-to-estimate process through four steps with human confirmation between each." Workflow Overview: 1. REQUIREMENTS EXTRACTION - extract scope, specs, quantities from documents (+ user confirms); 2. SCHEDULE BUILDER - create WBS and pricing schedule structure (+ user confirms); 3. LINE ITEM PRICING - price each item with workings (+ user confirms); 4. RECONCILIATION CHECK - verify completeness, prepare tender letter.
- t=07:48 Inside step 3 it goes through each individual line item and "creates a new agent for each of those individual tasks," looks at scope, reads the cost library to prepare an estimate, then a final completeness check. Frames 58-59 show the reconciliation-check sub-skill: "Final quality gate before tender submission," with a Requirements Coverage Check table (columns Req/BOQ ID, item, Status [Covered / MISSING], Schedule Item, Notes).
- t=08:19 Two ways to handle plugins. (a) Simple: a plugin is a file you upload. Go create plugin, upload a plugin; Claude has a specific plugin file format. To make one, "create plugin" then "create with Claude," describe the plugin, Claude builds it as a zip you share with your company. Frame 61 shows the "Upload local plugin" modal (drag-and-drop / Browse files, with a trust warning that uploaded plugins are not controlled by Anthropic).
- t=08:48 (b) Advanced ("the fancy way"): build a real plugin that syncs with an online database using Claude Code + GitHub. GitHub described as an online file-sharing system big software companies use for code bases.
- t=09:34 Tim's own repo: "Tim F operating system" (frames 67-71 show github.com/timothyfairley/timfOS, "My personal Operating System," folders: connections, context, rules, scripts/youtube, skills, src.example, .gitignore, .mcp.json). Not construction-specific; built around his YouTube channel automations / Claude routines. He stores individual skills there and installs the repository as a Claude plugin.
- t=09:57 The build flow in Claude Code: switch to the Claude Code tab (frames 64-74 show "Welcome back, Tim" with Sessions and Pull requests, e.g. "Add weekly-progress-report skill for portfolio digest," "Optimize batch operations and add database indexes"). Build the individual skills first and get the workflows right (a library of ~20 skills), then tell Claude: build a Claude Code plugin that pulls all my individual skills, explain what software to connect, store as a plugin, push to your GitHub repository.
- t=10:27 Back in Cowork: Customize > Plugins > Create a plugin > Add marketplace, then select/copy in your GitHub repository (frames 76-77 show the "Add marketplace" modal, URL field "Select a repository," trust warning, Cancel / Sync). Result: an online shareable repository of all your skills the whole team can install.
- t=10:46 Maintenance: keep it up to date; when someone changes/approves something, an update button appears and everyone in the company pulls the newest library of skills.
- t=11:04 Close: plugins give everyone in your company a "construction brain" on their Claude account.

## On-screen tools and Claude skills/plugins (table; names EXACTLY as shown on screen)

| Name on screen | Type | Where seen | Notes |
|---|---|---|---|
| Contractor os skills / contractor-os-skills | Plugin | frames 1,21,30,37-41,78,80; t=04:57 | "ContractorOS skills bundle. 27 construction skills..." Source: "Uploaded from file"; Version 0.1.2; Author ContractorOS; updated 8 days ago. Companion to contractor-os-setup. |
| Finance | Plugin | frames 29-34; t=04:38 | Marketplace (Anthropic & Partners); Version 12.0; Author Anthropic; updated 2 days ago. Skills: audit-support, close-management, financial-statements, journal-entry, journal-entry-prep, reconciliation, sox-testing, variance-analysis. |
| Productivity | Plugin | left rail frames 1-5 (Disabled) | Listed, not opened. |
| Engineering, Data, Product management, Operations, Sales, Legal, Pdf viewer, Brand voice | Plugins | Directory, frame 33 | Anthropic & Partners marketplace plugins. |
| bid-planner / Bid Planner | Skill | frame 3; t-n/a | Output artifacts shown: Bid Workbook (.xlsx 9 tabs), Bid Kick-off Deck (.pptx), Bid Folder (.zip). Trigger "Slash command + auto." |
| bid-presentation | Skill | frames 4,21 | |
| cashflow-forecaster / Cashflow Forecaster | Skill | frame 4 | "Build trade-aware cashflow forecasts from a contractor's package schedule." S-curve / RICS aware. |
| construction-takeoff | Skill | frames 6,21,39,55 | "AI-powered quantity takeoff from construction drawings. Extracts quantities across all trades." |
| contract-administrator / Contract Administrator | Skill | frames 5,21 | Two modes: Layer 1 Plan Builder. Triggers on revisiting a signed management plan. |
| contract-review / Construction Contract Review | Skill | frames 19-30,39 | Trigger "Slash command + auto"; Author You; updated Apr 22 2026. Covers NEC4, JCT, FIDIC, bespoke. Important note: assist only, not legal advice; do NOT draft amendments. |
| departures-register | Skill | frames 21,27,39 | "Generate a Subcontract Departures Register from a contract review." |
| completions-requirements | Skill | frames 4,21,54 | |
| document-controller | Skill | frames 19,39 | |
| gantt-chart | Skill | frames 19,55,59 | "Create interactive Gantt chart schedules with editable activities, dates, durations..." |
| reconciliation-check / Reconciliation Check | Skill | frames 19,58-59; t=07:48 | "Final quality gate before tender submission." Step 4 of estimating workflow. Requirements Coverage Check table. |
| estimating-workflow / Construction Estimating Workflow | Orchestrator skill | frames 54-57; t=07:11 | 4-step orchestrator with human confirmation between steps (extraction, schedule builder, line-item pricing, reconciliation). |
| schedule | Skill | frames 19,22 | |
| om-manual | Skill | frames 11,19,22 | O&M manual. |
| wrapup | Skill | frames 19,22 | |
| youtube-packaging | Skill | frames 19,22 | (Tim's channel ops, non-construction.) |
| procurement-packaging | Skill | frames 19,22 | |
| subcontractor-quote-analysis | Skill | frames 22-25 | |
| notebooklm / notebooklM | Skill | frames 22-25 | |
| dashboard-builder | Skill | frames 54,59 | "Scope and build construction dashboards inside Cowork." Bid pipelines, cost views, RFI trackers. |
| data-structurer | Skill | frames 54-55,59 | "Structure messy, unstructured construction data into clean, classified spreadsheets." |
| line-item-pricing | Skill | frames 55,59 | |
| monthly-cvr | Skill | frames 55,59 | Monthly cost-value reconciliation. |
| payment-claim, payment-claim-review | Skills | frames 3-5,55,59 | |
| pqs-cost-report | Skill | frames 56,59 | |
| prequalification-analyser | Skill | frame 55 | |
| rfi-drafter | Skill | frame 60 | |
| mcp-builder | Skill | frames 22-25 | Build an MCP server. |
| skill-creator / skill-creator | Skill | frames 22-25 | Meta-skill to author new skills. |
| cowork-plugin-customizer | Skill (Cowork) | frames 46-52; t=05:50 | Invoked when customizing a plugin; reads plugin.json, wires connectors. |
| Connectors: Snowflake, Databricks, Google Cloud BigQuery, Slack, Microsoft 365, Google Calendar, Gmail | Connectors / MCP | frame 35 | Install/Connect buttons. |
| timfOS (github.com/timothyfairley/timfOS) | GitHub repo used as plugin marketplace | frames 67-71; t=09:34 | Folders: connections, context, rules, scripts/youtube, skills, src.example, .gitignore, .mcp.json. |
| Add marketplace / Upload local plugin (modals) | Cowork plugin install UI | frames 61,76-77; t=08:19, 10:27 | "Add marketplace" takes a GitHub repo URL then Sync. "Upload local plugin" takes a drag-drop file. Both carry an Anthropic trust warning. |

## The workflow, step by step (reproducible how-to)

How the video says to do it, in order:

1. Build individual skills first. For each construction task, define input information, the data transformation, and the output format. Gather many real examples, iterate with Claude until the output format is exactly right, then tell Claude to "store this as a skill." Aim for a library of roughly 20 skills before bundling.
2. Use an existing plugin if one fits. In Cowork, Customize > Plugins; browse Anthropic's Directory (Finance, Engineering, Legal, etc.) or add a third-party plugin like ContractorOS. Installing exposes all its skills, which become callable by slash command + auto-trigger.
3. Customize the installed plugin to your business. In a Cowork chat, ask Claude to customize the named plugin and paste links to your data (Notion business context / rate library, or any connector: QuickBooks, Airtable, Google Drive, SharePoint). Cowork runs a plugin-customizer skill that edits plugin.json and wires the connector into the plugin's Context.
4. Compose skills into orchestrators and sub-agents. Build an orchestrator skill (e.g. estimating-workflow) that calls ordered sub-skills with a human confirmation gate between each step; for heavy steps, spin up a separate sub-agent per task / line item to run in parallel and protect the context window.
5. Package the plugin two ways:
   - Simple: Customize > Plugins > Create plugin > "Create with Claude," describe it, Claude emits a zip; or "Upload local plugin" to load a plugin file. Share the zip with the team.
   - Advanced (shareable + version-controlled): in the Claude Code tab, instruct Claude to build a plugin that pulls all your individual skills, state the software to connect, store it as a plugin, and push to a GitHub repository (Tim's is timfOS with skills/, connections/, context/, rules/, .mcp.json).
6. Publish as a marketplace and distribute. Back in Cowork: Customize > Plugins > Create plugin > Add marketplace > paste/select the GitHub repo URL > Sync. The whole team can now install the same plugin.
7. Maintain and roll out updates. When someone changes or approves a skill in the repo, an update button surfaces in Cowork and every teammate pulls the newest library.

## What works / what does NOT

Works (shown on screen):
- Slash-command + auto invocation of a skill from a Cowork chat ("review my contract using contract-review," frames 6,14).
- A skill rendering an interactive intake form (contract type / contracting side / contract form, frames 11-19).
- Installing a third-party construction plugin and seeing 27 named skills (frames 30,41,80).
- Plugin customization that adds a Notion connector to the plugin Context via a cowork-plugin-customizer skill (frames 46-57).
- The orchestrator + sub-skill + reconciliation pattern, fully visible in the estimating-workflow and reconciliation-check skill bodies (frames 54-59).
- Publishing a GitHub repo as a Cowork plugin marketplace and syncing (frames 76-77), and the Claude Code repo/PR view backing it (frames 67-74).

Does not / caveats observed:
- The plugin customization run threw a persistent "This isn't working right now. You can try again later" banner across frames 48-60; the demo continued but the live action visibly errored, so the customization success is asserted, not cleanly demonstrated end-to-end.
- Hooks are named only and never demonstrated; the video explicitly defers them to Claude Code and does not show one (t=04:09).
- Sub-agents are described conceptually (project-indexer as a spun-up agent) but no agent definition file or config is shown on screen.
- The spoken skill count ("30") does not match the on-screen plugin card ("27 construction skills"). Treat the count as approximate.
- This is a marketing/explainer video, not a build tutorial; it shows the concept and the UI surfaces, not the actual SKILL.md or plugin.json contents (the plugin.json is only referenced as a filename the customizer reads, frame 51).

## Concrete numbers, rates, file names, examples shown

- ContractorOS plugin: Version 0.1.2; Author ContractorOS; Source "Uploaded from file"; updated 8 days ago; "27 construction skills" (spoken "30").
- Finance plugin: Version 12.0; Marketplace (Anthropic & Partners); updated 2 days ago.
- contract-review skill: Author "You"; updated Apr 22 2026; trigger "Slash command + auto"; covers NEC4 / JCT / FIDIC / AIA-ConsensusDocs / CCDC / AS-Australian / bespoke.
- estimating-workflow / reconciliation-check / contract-administrator skills: updated May 8 2026; trigger "Slash command + auto."
- Payment-terms example: contract says 45 days, the firm's standard max is 30 days -> flagged in a departures register with a proposed amendment.
- Plugin/repo file names referenced: plugin.json (read by the customizer), .mcp.json, .gitignore (in timfOS).
- timfOS repo folders: connections, context, rules, scripts/youtube, skills, src.example.
- bid-planner outputs: Bid Workbook (.xlsx, 9 tabs), Bid Kick-off Deck (.pptx), Bid Folder (.zip).
- Notion URL shown: a "Bradman-Construction-Business-Context" notion.so page used as the customization data source.
- Connectors menu: Snowflake, Databricks, Google Cloud BigQuery, Slack, Microsoft 365, Google Calendar, Gmail; spoken connectors: Notion, QuickBooks, Airtable, Google Drive/Workspace, Microsoft SharePoint.
- Model shown in Cowork composer: "Opus 4.7."
- LADs red-flag heuristics in the contract-review body (frame 25): LADs exceeding 10% of contract value flagged as disproportionality risk; "no cap on LADs" flagged as open-ended exposure.

## Applicability to a structural steel fabricator (Your Company)

The biggest single transfer: this video is direct external validation of the architecture Your Company already runs. ContractorOS's estimating-workflow is functionally our `bid_chain` / bid pipeline (extract requirements -> WBS/pricing schedule -> per-line-item pricing with a spun-up agent per item -> reconciliation completeness gate), and its reconciliation-check Requirements Coverage table is exactly our `bridge/bid_sanity_gates.py` run_gates plus VirtualOwner review posture. Concretely:

- Plugins as the distribution layer we currently lack. Today our skills live in `skills/` and ship inside the EXE; there is no team-pull/version-control story. The video's pattern (skills authored individually, bundled into one plugin, pushed to a GitHub repo, added in Cowork via Add marketplace > Sync, with an update button for the team) maps onto turning our `skills/` directory (cowork-bid-estimate, vj-scan, spec-driven-development, project-indexer, drawing-analyzer, claude-design, etc.) into a single "YourCo-OS" plugin repo. That gives Owner and Joseph one synced library and a clean upgrade path, instead of rebuilding the EXE to ship a skill change. This is the most useful idea to steal.
- Orchestrator skill maps to our estimate pipeline, with a guardrail upgrade. Their 4-step orchestrator inserts an explicit "User confirms" gate between every step. Our pipeline already enforces verify-don't-generate and confidence tagging; adopting the same visible human-confirmation checkpoint between requirements-extraction, takeoff, AISC-validated pricing, and the sanity-gate reconciliation would make our governance gates first-class steps in the orchestrator rather than implicit. Their construction-takeoff skill is generic ("extracts quantities across all trades") and is exactly where our advantage lives: ours must route member quantities through `bridge/aisc_validator.py` (2,299-shape v16.0 DB), never trust LLM math, and apply the SF-sourcing rule. Their takeoff would be a regression for us if adopted as-is.
- Sub-agents per line item maps to our existing background-thread + job_id pattern. The video's "spin up a separate agent per line item to protect the context window" is the Cowork-native version of what CLAUDE.local.md already describes for vj_scan_and_fix_async. For us this is most useful for parallelizing a member takeoff across drawing sheets (our drawing-analyzer / project-indexer already split per-sheet), where each sub-agent reports counts back to a reconciliation gate. Note our hard rule: no classes defined inside functions, and sub-agents must still funnel numbers through the validator, not produce system-of-record tonnage themselves.
- Connectors / MCP. Their connector story (Notion, QuickBooks, Airtable, SharePoint, Snowflake, etc. via Cowork connectors) is the MCP layer. We already ship `mcp_server.py` sharing the Bridge class; the transferable move is exposing our Bridge methods and rate/AISC data as MCP resources so a plugin can wire them the way they wire Notion, rather than us reading raw files. Their cost-library-in-Notion pattern is a security anti-pattern for us: BID_RATES are CEO-locked in `bridge/bid_rates.py` and MATERIAL_COSTS/supplier names are Tier-1 internal-only, so our "rate library" must stay in-repo and validator-gated, never in a third-party Notion/QuickBooks connector that could surface on client output.
- Hooks. Named but undemonstrated, and Cowork-unavailable (Claude Code only). We already use `.githooks/pre-commit` and the `validate_bid_output.py` export gate, which are the right home for the same intent (block a client PDF with no page-1 render, enforce no-em-dash / no-supplier-name). No change needed; just recognize hooks are our pre-commit + export-gate layer, not a new Cowork feature to chase.

What does NOT transfer: the generic construction-takeoff (must be AISC-validated for steel), the cloud cost-library-in-Notion (violates our rate-lock and Tier-1 supplier confidentiality), and the casual "tell Claude to store this as a skill" authoring loop (our skills carry governance and must pass self-test 92/92 and vj-scan, so skill authoring stays a reviewed code change, not an ad-hoc chat artifact). The ContractorOS plugin itself is a competitor product, not something to install.

## Caveats

- Frame sparsity: 80 frames over 11:17 is ~1 frame per 8.5s; the watch tool itself warns accuracy degrades past 10 minutes. Fast UI actions (menu clicks, the exact moment a connector attaches) fall between frames, so some UI transitions are inferred from adjacent frames plus the caption text rather than directly seen.
- The customization step errored on screen (recurring "This isn't working right now" banner, frames 48-60), so its successful completion is the narrator's claim, not a frame-verified result.
- Title encoding: the report header shows a stray character where an en-dash sits in the YouTube title; the actual title uses dashes.
- Skill-count discrepancy (spoken 30 vs on-screen 27) is unresolved; 27 is the on-screen value.
- Several skill names in the left rail are read from a 512px frame and may have minor spelling artifacts (e.g. notebooklm vs notebooklM); names are transcribed as best read.
- No SKILL.md, plugin.json, or hook/agent config file contents were shown; structural detail about the plugin file format is described verbally only (zip file; specific Claude plugin file format; GitHub repo with .mcp.json).
