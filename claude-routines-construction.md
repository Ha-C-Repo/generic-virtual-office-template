# Claude Routines for Construction (Your Company Adaptation)

Source: two research videos, May 2026. "8 Claude Routines for Construction"
and "The COMPLETE Guide to Construction Project Management."

Use when: planning autonomous or scheduled AI agents for Your Company ops.

Relationship to existing files in this project:

- `.specify/specs/bid-estimating/scheduled-tasks.md` is the live routines
  spec. Three cron tasks are already registered there. The 8 routines below
  are the next-tier roadmap.
- `.specify/specs/bid-estimating/mcp-connectors.md` is the live connector
  spec. Any routine that reads or writes cloud data must register through
  one of those connectors.
- `.specify/specs/bid-estimating/RESEARCH-PAPER-and-HANDOFF.md` is the
  underlying market and feature research these routines map against.
- `rates-and-pricing.md` holds the locked Q2 2026 rates that any pricing
  routine must call, not regenerate.
- `owner-rules.md` is the bid-rule gate every outbound routine must pass.
- `brand-voice.md` is the voice gate every email or document routine must
  pass.
- `skills/change-order/` is the existing change-order skill. Routine 6 and
  routine 7 feed it.
- `skills/bid-orchestrator/`, `skills/bid-pricing/`, and
  `bridge/bid_pipeline.py` are the existing bid intake and pricing
  surfaces. Routine 2 feeds them.

---

## The one rule that governs everything

An autonomous routine can only read and write data that lives in the cloud.
Desktop files are invisible to it. Before building any routine, the data it
needs must sit in M365 (SharePoint or OneDrive), Google Drive, or
Gmail/Outlook. A routine pointed at a desktop folder will fail silently.

This is the same constraint `mcp-connectors.md` already documents for the
filesystem connector. Any routine added here must be reachable through one
of the registered connectors or it does not run.

---

## Routines vs Cowork (do not conflate)

The videos demonstrate Claude routines: a prompt plus a cloud environment
(typically a GitHub repo) set to run on a schedule or an event trigger,
even with the computer off. Cowork is the desktop file and task tool. Both
can host these workflows. The decision is which host, not whether the
workflows are valid.

---

## Stack rule (hard)

The videos use Notion, Airtable, and QuickBooks. Do not add those.

- Register and database role: SharePoint List or a OneDrive-stored xlsx
  or markdown. M365, already paid.
- Email source: Outlook (owner@yourcompany.example.com), already connected.
- Send actions: route through the Zapier integration once a connector is
  registered in `mcp-connectors.md`. Do not assume it is configured. Verify
  before building.
- Accounting source for cost tracking: not yet confirmed. See open
  questions.

---

## The correspondence register is the spine

The core architecture from the videos: one register logs every project
email. Every other routine reads from the register, not from the raw
inbox. This makes each downstream routine faster and gives Claude project
context for free. Build the register first. Everything else hangs off it.

---

## The 8 routines mapped to Your Company

| # | Routine | What it does | Your Company source on current stack | Build now? |
|---|---|---|---|---|
| 1 | Email manager | Logs project emails into a searchable register, flags commercial items | Outlook to SharePoint List | Yes. Build first. |
| 2 | CRM auto-updater | Extracts client, tender date, value, site-visit date from new inquiries | New tender drop to `bridge/bid_pipeline.py` and `skills/bid-orchestrator/` | Yes |
| 3 | Cost tracker | Matches actual hours and expenses to budget, runs earned value | Needs accounting export plus the 11 hrs/ton baseline from `rates-and-pricing.md` | Blocked. See open questions |
| 4 | Project context refresh | Scans register and files, builds running project knowledge by CALLING `.claude/skills/project-indexer/SKILL.md` (already built). Routine 4 is the schedule and trigger, project-indexer is the executor. Do not build a parallel mechanism. | Register plus OneDrive project folders | Yes |
| 5 | Payment claim generator | Builds monthly pay app from percent complete vs prior month | Needs SOV or G702-G703 template plus progress data | Partial. Needs templates |
| 6 | Weekly progress reporter | Drafts client status email from registers, gated by `brand-voice.md` | Register plus variation and weather logs | Yes, once register exists |
| 7 | Weather log | Pulls weather, logs inclement days vs contract threshold, flags EOT for `skills/change-order/` | Free weather API to OneDrive log | Yes. Relevant to erection scope |
| 8 | Meeting minutes | Indexes verbal client instructions into the register | Teams transcripts to register | Yes |

Priority order: 1, then 4 and 8, then 2, then 6 and 7, then 5 and 3 once
their data sources exist.

---

## PM framework concepts worth adopting

Only the items that change how Your Company already works. The rest of the
guide is general education and is not repeated here.

- Estimate tiers by phase. Rough order of magnitude (plus or minus 30%)
  for early feasibility, detailed (plus or minus 10%) at tender. Useful
  language for fast-vs-firm quote distinctions.
- Earned value. Planned value, earned value, actual cost. This is the
  math behind routine 3. Pairs with the 11 hrs/ton baseline once
  accounting data is reachable.
- Variation register and weather log feed delay and change-order claims.
  Both link to `skills/change-order/`. The weather log (routine 7) is the
  cleanest EOT evidence.
- Scope, inclusions, and exclusions stated in every estimate prevent
  losses. This already matches the bid document rules in
  `owner-rules.md`.

---

## How to build a routine (process from the videos)

1. Build it as a manual Claude skill first. Test it repeatedly until the
   output is right.
2. Only then save it as a skill and push it to the cloud host so it runs
   autonomously.
3. Do not start by trying to build the routine. Start by getting the
   manual workflow correct.

This is the same path the existing skills under `skills/` were built
along.

---

## Open questions for Owner or Joseph

1. Accounting source for routine 3. Which system holds actual cost and
   hours, and is it cloud-reachable? This unblocks cost tracking and
   earned value.
2. SOV or pay-app template. Does Your Company submit AIA G702-G703 or a
   client form? Routine 5 needs one template to match against percent
   complete.
3. Host decision. Claude routines via GitHub, or Cowork on a designated
   machine? This sets where the register and skills live.
4. Zapier send. Is the Outlook/Gmail send integration registered as a
   connector in `.specify/specs/bid-estimating/mcp-connectors.md`, or is
   that still a manual step? Routines 1, 2, 6, and 8 depend on the
   answer.
