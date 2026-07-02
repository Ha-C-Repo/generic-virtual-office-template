# Your Company - Cowork Governance Repo

Private repo for the engineering-governance layer over the Your Company Cowork project. Additive and backup-first.

It does not contain or replace the eleven construction skills already in Cowork (requirements-extraction, contract-review, departures-register, construction-takeoff, document-controller, procurement-packaging, gantt-chart, reconciliation-check, line-item-pricing, schedule-builder, estimating-workflow). It governs them and adds two new skills the source series recommends.

## What is here
- `.specify/governance-delta.md`      Five review gates plus the verify-don't-generate rule. Additive to the existing constitution.
- `0.ai-context/CLAUDE.md`            Template per-project loader and operating rules.
- `.claude/skills/project-indexer/`   New skill: builds the per-project context layer.
- `.claude/skills/drawing-analyzer/`  New skill plus a deterministic PDF script. Keeps the model off the pixels.
- `.claude/skills/governance/references/`  Pre-mortem, dependency audit, verification step, domestic material.
- `.claude/skills/governance/scripts/validate_bid_output.py`  Deterministic pre-export checks.
- `_handoff/changelog.md`             One line per change.

## Hard rules for this repo
- Never commit client data, drawings, the rate library, supplier names, or API keys. `.gitignore` blocks the common cases. If in doubt, do not commit it.
- The eleven existing skills are not in this repo. Edit them in Cowork. This repo holds the governance layer and the two new skills.
- Skills install from `.claude/skills/<name>/SKILL.md` at the project root, or `~/.claude/skills/<name>/` for user-global. Not a root `.skills/` folder.

## Install
1. Copy `.claude/skills/project-indexer` and `.claude/skills/drawing-analyzer` into your project `.claude/skills/` (or user-global).
2. Copy `.specify/governance-delta.md` next to your existing `.specify/constitution.md`.
3. On a new job, run project-indexer to generate `0.ai-context/`.
4. Fold the operating rules into the generated `0.ai-context/CLAUDE.md`.
5. Run `validate_bid_output.py` before any client PDF export.

## Rollout phases (from the handoff)
P1 governance-delta. P2 fix any `.skills/` path to `.claude/skills/`. P3 context architecture. P4 operating rules into CLAUDE.md. P5 governance reference docs. P6 domestic-material block into procurement-packaging and line-item-pricing. P7 point skills at AISC v16.0 and the rate library. P8 this private repo plus offline routines.

## Supplier and precedent lists (local-only)
The validator's supplier-name and precedent-project checks are deterministic when a list is present and MANUAL when it is not. The lists hold commercial data, so they never enter the repo.

- Copy `.claude/skills/governance/data/suppliers.example.txt` to `suppliers.local.txt` and fill it in. Same for `precedents.example.txt`.
- `*.local.txt` is gitignored, so the real lists stay out of version control.
- Or keep the lists anywhere (a OneDrive path, say) and point to them: `--suppliers PATH --precedents PATH`, or the `YOURCO_SUPPLIER_LIST` and `YOURCO_PRECEDENT_LIST` environment variables.
- Resolution order per list: flag, then env var, then the default `data/<name>.local.txt`. If none is found, the check stays MANUAL rather than failing.
