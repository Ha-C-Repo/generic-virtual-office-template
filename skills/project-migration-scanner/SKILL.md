---
name: project-migration-scanner
description: >
  Two-pass scanner to seed historical project data from an existing file system.
  Pass 1 is read-only inventory. Pass 2 copies files to project folders on
  explicit per-project instruction only. Use when Joseph says "scan projects"
  or "migrate project files".
triggers:
  - scan projects
  - migrate project files
  - seed project data
  - scan my project folder
  - find existing projects
  - inventory project files
---

# Project Migration Scanner

## Triggers

Fire this skill when the user message contains any of:
- "scan projects"
- "migrate project files"
- "seed project data"
- "scan my project folder"
- "find existing projects"
- "inventory project files"
- "scan pass 1"
- "scan pass 2"

## Context

Used to bring historical project data into the Your Company project schema.
Joseph runs this when setting up a new machine or migrating files.

## Two-Pass Design

### Pass 1 - Read-Only Inventory

Scans a root directory and produces an inventory report. NEVER writes, moves,
or copies any file. No exceptions.

Output: structured inventory with:
- Confirmed matches (fuzzy score >= 0.70 against known project list)
- Unknown folders (score < 0.70 - do not auto-categorize)
- Vendor documents (flagged only - do not copy to project folders)
- Client documents (flagged only - require per-project Owner approval)
- File counts and total size per folder

### Pass 2 - Copy Only

Runs only on explicit per-project instruction. Never automatic.

Rules:
- Copy only. Never move. Originals stay in place.
- Client docs: do not copy without the Owner's explicit per-project approval.
- Vendor docs: do not copy to project folders. Flag in inventory.
- Unknown folders: do not auto-categorize. Surface to Joseph for decision.
- API Keys/ directory: never touched under any circumstances.
- Supplier names: never written to any project document.

## Hard Constraints

1. Pass 1 is always read-only. No exceptions.
2. Pass 2 never runs without explicit instruction. Never automatic.
3. Copy only. Originals stay in place.
4. Fuzzy match threshold 0.70. Below threshold goes to unknown list.
5. API Keys/ directory: do not scan, do not list, do not copy.
6. No supplier names in output documents.
7. Gate 4 range recalibration only after 3+ real projects provide ratio data.

## After Output

After Pass 1:
- State: "Pass 1 complete. X confirmed projects, Y unknown folders, Z flagged vendor docs."
- For each unknown folder: "Unknown: [folder name] - score [N]. Assign to a project or skip?"
- Do not proceed to Pass 2 without explicit instruction per project.

After Pass 2 (if approved):
- State: "Copied [N] files to [project name]. Originals remain at [source path]."
- List every file copied with source and destination.
