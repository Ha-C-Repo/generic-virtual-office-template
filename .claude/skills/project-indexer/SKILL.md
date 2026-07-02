---
name: project-indexer
description: Build the per-project AI context layer for a construction job. Run once on a new project to convert every static document and the drawing set into a 0.ai-context folder holding CLAUDE.md, project.md, drawings.md, and memory.md; living documents (registers, WIP, schedules) are listed, never mirrored. Use when starting a new project, when documents change, or when the user says index the project, build the context, or set up the project. Cuts query token use roughly 20 to 40 times after the first run.
---

# Project Indexer

## Input
The project folder: contract, specifications, drawings, registers.

## Process
1. Use Haiku or Sonnet for extraction, not Opus.
2. Create `0.ai-context/` at the project root if absent. Confirm before overwriting an existing one.
3. Write `project.md`: a structured snapshot. Scope, contract type, payment terms, key dates, and status as of the index date, stamped with that date. Live questions (current status, register contents, WIP, schedules) are never answered from project.md; read the sources listed in the LIVE DOCUMENTS section (P13). For BIDS, seed it from the takeoff. For AWARDED jobs, seed it from the signed contract and include a contract terms summary: parties, contract sum, payment schedule, retainage, notice periods, key dates.
4. Write `drawings.md`: one line per drawing with discipline, sheet number, title, and what to find on it. Record cross-references between sheets. For heavy drawing sets, call the drawing-analyzer skill first, with its output directory set inside `0.ai-context/drawing-extracts/` so no artifact lands beside the raw drawings. Keep the one-line-per-sheet format. Do NOT create per-sheet markdown files; that is a benchmarked future item (KB4).
5. Write `CLAUDE.md` from the template: the loader and operating rules, pointing to the constitution, project.md, drawings.md, memory.md. Include a mandatory LIVE DOCUMENTS section: list every register, WIP file, and schedule in the project folder, each with its path, under the rule "always read the source file, never a mirror" (P13). Static documents (signed contract, specs, issued drawings) get markdown mirrors. Living documents never do. Mirrors of static documents live under `0.ai-context/`. Write or overwrite any file named CLAUDE.md via `.claude/skills/governance/scripts/safe_write.py` (--from, --stdin, or --content), never via raw Write or Edit: the Cowork watcher races chunked writes on that filename and silently truncates at about 4 KB. The script backs up first and verifies byte count.
6. Create an empty `memory.md` for end-of-chat summaries, only if absent. Never reset or regenerate memory.md on a re-run; reprocessing refreshes project.md, drawings.md, and CLAUDE.md only.
7. Report the token cost of this first index and confirm before reprocessing on later runs.

## Output
`0.ai-context/` with CLAUDE.md, project.md, drawings.md, memory.md.

## Rules
Ask clarifying questions if the folder structure is unclear. State confidence on any extracted figure. Do not paste the rate library into these files; point to it (P10). The indexer writes project content only inside `0.ai-context/`. The sole exceptions are the pre-overwrite backup snapshot to `_handoff/backups/<UTC-ISO-timestamp>/` and its changelog line, per the Operating Rules. The raw project data layer is read-only to this skill.
