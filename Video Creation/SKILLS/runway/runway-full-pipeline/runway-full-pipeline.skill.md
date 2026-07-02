---
name: runway-full-pipeline
description: Orchestrates the entire Runway Workflow build for a multi-clip video project. Reads 04_runway_prompts.md, opens Runway, creates a new Workflow named after the project, generates 1-3 reference images on Nano Banana Pro, generates 6+ Gen-4.5 video clips wired to those references, builds Stitch + TTS + Add Audio. Continuously writes progress to RUN_STATE.md (or SESSION-RESUME.md if DRIVE_MODE=manual-handoff). Use as the single entry point for any clean video build.
---

# Skill: runway-full-pipeline

## When to invoke

User says:
- "Build the 30s video in Runway"
- "Run the full pipeline for <project name>"
- "Open Runway and produce the video from 04_runway_prompts.md"

## Inputs

Required:
- `project_name` — the folder name under `ACTIVE_PROJECTS/`.

Optional:
- `quality` — "standard" (default) or "final_quality" (2.4x credit cost).
- `aspect_ratio` — "9:16" (default for LinkedIn / Reels), "16:9", "1:1".

## Pre-flight checks

i.    `ACTIVE_PROJECTS/<project_name>/06_qa_checklist.md` exists and all 20
      items show pass.
ii.   `04_runway_prompts.md` parses cleanly (six clip prompts plus reference
      prompts).
iii.  Owner approval received before any public release.
iv.   Credit balance covers the full estimated spend in `05_workflow_plan.md`.
v.    Browser is connected.

## Procedure

### 1. Open Runway and create the workflow
Navigate to `https://app.runwayml.com/video-tools/teams/<team>/ai-tools/workflows`.
Click `+ New Workflow`. Name it `<project_name>` (e.g.
`YourCo_30s_LinkedIn_Pilot`). Save.

### 2. Parse the prompts file
Read `04_runway_prompts.md`. Extract:
- Reference image prompts (named A, B, C in the standard template)
- Six clip prompts (named Clip 01 through Clip 06)
- For each clip, which reference image it uses as First Video Frame

### 3. Initialize RUN_STATE.md
Copy `SKILLS/runway/runway-persistent-driver/RUN_STATE.template.md` to
`ACTIVE_PROJECTS/<project_name>/RUN_STATE.md`. Set DRIVE_MODE =
`claude-autonomous`. Fill in project metadata and the empty wave-status
table. (If you need to flip to manual handoff later — auth, payment,
two consecutive node failures, hardware — write SESSION-RESUME.md and
set DRIVE_MODE = `manual-handoff` per CLAUDE.md PERSISTENT EXECUTION
DISCIPLINE.)

### 4. Generate reference images
For each reference (A, B, C as applicable):
- Invoke `/runway-image-auto` with the reference prompt.
- Capture the returned `image_source_handle_id`.
- Update RUN_STATE.md (WAVE_1 row for this NBP).
- If generation fails, surface to user and pause for guidance.

### 5. Generate video clips
For each Clip 01-06:
- Determine which reference image is the First Video Frame source from
  04_runway_prompts.md.
- Invoke `/runway-video-auto` with the clip prompt and the source handle id.
- Update RUN_STATE.md (WAVE_2 row for this clip) after each clip's completion.
- Frame-by-frame scrub the clip output. If artifacts found, regenerate just
  that clip up to two times before surfacing to user.

### 6. Build Stitch
Invoke `/runway-stitch-auto` (subskill) with the 6 video-source handle ids
in time order.

### 7. Build TTS and Add Audio
- Add a Text node, populate with the VO script from `02_script.md`.
- Add a Text to Speech node, wire Text → TTS input.
- Add an Add Audio node, wire Stitch video → Add Audio video input,
  TTS audio → Add Audio audio input.

### 8. Drive the chain to completion — never press "Run all"

**DO NOT press the top-bar "Run all" button.** Run all restarts every node from scratch, burns credits regenerating cached outputs, and triggers "node not yet successfully run" validation errors when wires lag the chain. See CLAUDE.md → RUNWAY RUN-ORDER DISCIPLINE.

Instead, invoke `/runway-persistent-driver` to drive the build wave by wave. It manages RUN_STATE.md, schedules check-ins between long generations, and respects Runway's concurrency limits. If the persistent driver is unavailable, run each terminal node individually in this order:

```
Wave 1 — NBPs            pairs of 2 concurrent, wait between pairs
Wave 2 — Gen-4.5 clips   pairs of 2 concurrent, wait between pairs
Wave 3 — Text-to-SFX     all 6 in parallel (audio is cheap)
Wave 4 — Add SFX To Clip N   sequentially as upstream completes
Wave 5 — TTS             single node
Wave 6 — Stitch          single node
Wave 7 — Master Add Audio    single node — the FINAL MASTER output
```

Click each individual node's own Run button. Do not press Run all. Cached upstream outputs feed forward automatically.

### 9. Final QA scrub
Click play on the Add Audio output. Watch the full 30 seconds.
Check against the QA checklist:
- Hook lands in first 3 seconds
- CTA in final 5 seconds
- No text gibberish in any frame
- No silhouetted or middle-distance humans
- Style consistent across all 6 clips
- Audio mix balanced, VO clear over music

### 10. Update RUN_STATE.md and 07_handoff_to_runway.md
Mark all rows in the wave-status table as "done" in RUN_STATE.md. (If
DRIVE_MODE = manual-handoff, update SESSION-RESUME.md instead.)
Update 07_handoff_to_runway.md with the final Runway export URL and any
notes for the post-production editor.

### 11. Surface to user
Return a [BRIEF] status block to the parent context summarizing:
- Total credits spent
- Each clip's QA result
- Open issues, if any
- Next concrete action (typically: export from Runway, then hand to editor
  for caption burn-in and three-crop export)

## Failure modes

If any sub-skill fails twice in a row, stop and surface to user. Do not
burn additional credits without guidance.

If session crashes mid-build, the next session reads RUN_STATE.md
(or SESSION-RESUME.md if DRIVE_MODE=manual-handoff) and continues from
the row marked "running" / "in progress."

## Output format

```
[BRIEF]

Brief for Owner:
  Finding:        Full Runway build complete for <project_name>.
                  6 clips generated, stitched, audio mixed.
  Recommendation: Export the master from Runway, hand to editor for
                  post-production (captions, end card, three-crop).
                  Owner approval still required before LinkedIn upload.
  Omitted:        Captions, end-card composite, three-crop export are
                  outside Runway scope (per CLAUDE.md project rules).
  Risk:           If any subtle artifact slipped past the frame-by-frame
                  scrub, it will surface in the editor preview. Inspect
                  on a large monitor before exporting from the editor.
```

## Related skills
- `/runway-image-auto` — invoked per reference image
- `/runway-video-auto` — invoked per video clip
- `/runway-stitch-auto` — invoked once for Stitch + Audio
- `/style-01-corporate-cinematic` through `/style-05-minimal-product` —
  upstream prompt generators
- `/format-30s-commercial` through `/format-brand-film-60s` —
  upstream format scaffolds
