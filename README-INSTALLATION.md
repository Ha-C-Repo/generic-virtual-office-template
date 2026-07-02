# YourCo Virtual Office - Architecture Upgrade Package

Six features adapted from the Build Co. portable architecture set, grounded in the
YourCo reference document (rates, stack, voice, compliance, topology). Plus the
sequential thinking MCP as a 7th feature (see sequential-thinking/ below).

No invented stack. No invented business facts.

**Revision, May 2026:** adds three workflow features above the original set: `workspace-handoffs` (cross-session intent: grill-with-docs, handoff, prototype), `clean-code-discipline` (defends the bridge from AI-driven code entropy), and `software-factory` (AFK sandbox execution discipline). All three are grounded in the existing Python/PyInstaller stack and the constitution. Nothing new to install beyond copying the folders.

**Revision, May 2026 (b):** adds `recurrent-orchestrator`, a bounded anchor-injected refinement loop for deep multi-step work (long takeoffs, multi-tab spreadsheet reconciliation). It freezes the binding constraints to `.specify/scratch/anchor.md`, re-reads them on every pass, and purges only `.specify/scratch/` at the end. It never touches `.specify/constitution.md` or `.specify/thinking_protocol.md`. It composes with spec-driven-development, sequential-thinking, and nemo-guardrails rather than replacing them. The neural-network framing of the source idea (KV-cache compression, drift immunity) was dropped as not applicable to a file workflow.

---

## What this package is

The YourCo virtual office is a compiled Python/PyInstaller Windows application.
The "code" is Python source with 471 Bridge methods and 25 skill files. These seven
directories add a spec-and-governance layer above the existing system.

---

## File placement

| File in this package | Goes here | Notes |
|---|---|---|
| `.specify/constitution.md` | Root of the YourCo project folder | New anchor layer. Read before any engineering task. |
| `skills/spec-driven-development/SKILL.md` | `skills/` folder | Add to skill registry in CLAUDE.md. |
| `skills/bid-orchestrator/SKILL.md` | `skills/` folder | Replaces linear bid chain. |
| `skills/nemo-guardrails/SKILL.md` | `skills/` folder | Runtime guardrail spec. |
| `skills/deployment-pipeline/SKILL.md` | `skills/` folder | PyInstaller promotion chain. |
| `skills/sequential-thinking/SKILL.md` | `skills/` folder | Pre-task deliberate reasoning. |
| `skills/workspace-handoffs/SKILL.md` | `skills/` folder | grill-with-docs, handoff, prototype. Cross-session intent. |
| `skills/clean-code-discipline/SKILL.md` | `skills/` folder | Deep modules, minimalism, surgical edits on the 471-method bridge. |
| `skills/software-factory/SKILL.md` | `skills/` folder | AFK sandbox runs on the dev workstation. iMac is never a sandbox. |
| `skills/recurrent-orchestrator/SKILL.md` | `skills/` folder | Bounded anchor-injected loop for deep multi-step work. Scratch under `.specify/scratch/` only. |
| `02_Wiki/Infrastructure/devops_master_manifest.md` | `02_Wiki/Infrastructure/` | Book of Secret Knowledge for the 3-machine topology. |

---

## Install order

1. Place `.specify/constitution.md`. Anchor first.
2. Copy all nine `skills/` folders into the YourCo skills directory.
3. Update CLAUDE.md with routing entries for the new skills (including workspace-handoffs, clean-code-discipline, software-factory, recurrent-orchestrator).
4. Place `devops_master_manifest.md` in the Infrastructure wiki folder.
5. Test: start a new Claude Code session, read the constitution, and ask it to describe the bid rates. Confirm it returns the CEO-locked values without deviation.

---

## What needs the Owner's sign-off

The constitution records Joseph as author. Principle 3 (bid rates) and Principle 1
(AISC data boundary) are the highest-stakes rules. Confirm with Owner before treating
the constitution as final.

## Two-company hygiene reminder

All YourCo files stay in the YourCo project folder. None of these files reference
Build Co. or Pinnacle content. The firewall runs in both directions.
