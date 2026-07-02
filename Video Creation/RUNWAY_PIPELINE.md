# Claude in Chrome + Runway — The Complete Video Pipeline

*Adapted from AKCodez's Higgsfield + Playwright UGC pipeline, 2026-05-20.
Tailored to Runway Workflows, Gen-4.5, Nano Banana Pro, the Your Company
visual system, and the 16 Anti-AI Laws.*

Automate the entire AI video production workflow: reference image generation,
clip generation, stitching, audio, and post-handoff. No tab switching, no
copy-pasting, no manual clicking. One command, full pipeline.

---

## Pre-analysis: watch the reference first (/watch)

Before generating anything from a reference video, analyze it with the /watch
skill (Claude Code) to pull the actual pacing, cuts, hook structure, and shot
list, then feed that into the creative brief. Do not infer a reference from its
title or thumbnail. /watch reads the footage frame by frame, so this is the read
step that precedes Runway generation. Production stays in this studio. Analysis
comes from /watch. Typical use: /watch reference_video.mp4 analyze the pacing,
cuts, and hook structure, then carry the result into CREATIVE_BRIEF. See the
CLAUDE.md "Video Analysis (/watch)" section.

## Overview

Claude (running in Cowork mode) has a Chrome extension that gives it control
over a real Chrome browser, plus a library of project-specific skills. Combined,
it can:

i.    Generate brand-locked reference images on Nano Banana Pro inside Runway.
ii.   Build a node-graph Workflow with 6+ Gen-4.5 video clips wired to the
      same reference image.
iii.  Apply the matching Style token to every prompt verbatim.
iv.   Stitch the clips, add TTS voiceover and SFX, and export.
v.    Run frame-by-frame artifact scrubs against the 16 Anti-AI Laws.
vi.   Hand off to the editor for post-production (captions, end card, three-crop
      export) and to Owner for executive approval before LinkedIn upload.

You define the project rules in `CLAUDE.md` and per-skill `SKILL.md` files.
Claude reads them every session.

---

## What's in the Studio

### Existing project assets
- `CLAUDE.md` — top-level project rules (16 Anti-AI Laws, 5 Style systems, pipeline)
- `SKILLS/VIDEO_STUDIO.md`, `SKILLS/ANTI_AI.md`, `SKILLS/RUNWAY.md` (reference docs)
- `TEMPLATES/30s_COMMERCIAL.md`, `15s_PREROLL.md`, `BRAND_FILM_60s.md`, etc.
- `ACTIVE_PROJECTS/<Name>/` — per-project working files (01_brief through 07_handoff)
- `OUTPUTS/<Name>/` — final approved deliverables
- `ASSETS/brand/` — logos, brand colors, guidelines
- `TOOLKIT/` — MCP scripts for driving Runway via Chrome MCP

### New skills (this pipeline)

| Category | Skill name | What it does |
|---|---|---|
| Pipeline | `/runway-full-pipeline` | End-to-end orchestrator: prompts → references → clips → stitch → audio |
| Pipeline | `/runway-image-auto` | Automates Nano Banana Pro image generation inside Runway Workflows |
| Pipeline | `/runway-video-auto` | Automates Gen-4.5 Text+Image to Video clip generation |
| Pipeline | `/runway-stitch-auto` | Wires clips → Stitch → Add Audio pipeline |
| Style | `/style-01-corporate-cinematic` | Style 01 prompt generator (B2B, legal, finance, professional services) |
| Style | `/style-02-luxury-premium` | Style 02 prompt generator (luxury / premium, navy + gold) |
| Style | `/style-03-documentary` | Style 03 prompt generator (Sony FX3, handheld) |
| Style | `/style-04-bold-energetic` | Style 04 prompt generator (RED Komodo, high contrast) |
| Style | `/style-05-minimal-product` | Style 05 prompt generator (studio, white BG) |
| Format | `/format-30s-commercial` | 30-second 6-clip commercial scaffold |
| Format | `/format-15s-preroll` | 15-second 3-clip pre-roll scaffold |
| Format | `/format-vertical-reel` | 9:16 vertical 3-6 clip Reel/TikTok scaffold |
| Format | `/format-brand-film-60s` | 60-second 10-12 clip brand film scaffold |
| Format | `/format-product-demo` | Product Shot Builder + Gen-4.5 clip product demo |

---

## Requirements

- Cowork mode (Claude desktop app with Chrome extension and shell access)
- Chrome with the Claude in Chrome extension installed and connected
- Runway account with Workflows access (Unlimited plan recommended)
- Project folder mounted in Cowork (this folder)
- Brand assets in `ASSETS/brand/`

---

## Setup (one time)

### Step 1. Connect the Chrome extension
i.  Install the Claude extension in Chrome.
ii. Open the Cowork desktop app, mount the `Video Creation` folder.
iii. Verify the connection via `mcp__Claude_in_Chrome__list_connected_browsers`.

### Step 2. Verify the toolkit
i.  `TOOLKIT/RUNWAY_MCP_TOOLKIT.md` describes the patterns that work.
ii. `TOOLKIT/scripts/inspect_canvas.js` orients each session.
iii. `TOOLKIT/scripts/get_handle_coords.js` returns precise drag coordinates.
iv.  `TOOLKIT/scripts/wire_handles.js` is the JavaScript fallback for wiring.

### Step 3. Read `CLAUDE.md`
The top-level `CLAUDE.md` already encodes:
- The eight-step production pipeline (Intake → Brief → Script → Shot List → Prompts → Workflow → QA → Deliver)
- The 16 Anti-AI Laws
- The five Style systems with verbatim style tokens
- The pre-generation QA checklist
- The approval chain (Owner final approval before public release)

This document extends that with Runway-specific automation rules.

---

## The Layout-First Build Discipline (LFB)

**Hard rule from Joseph (2026-05-20):** Plan and place every node first. Wire every connection. Verify every ∞ toggle. Only then populate Text inputs and start generations.

### Why
- Stacking new nodes on existing ones causes click errors and lost time.
- Running mid-build risks burning credits on misconfigured chains.
- Runway caps concurrent video generations at 2; sequencing matters.
- A clean canvas survives long-running sessions and lets a co-worker pick up the build.

### LFB Sequence (do not deviate)

i.    **Plan the layout** before opening Runway. Sketch a grid: one row per clip, references and Text nodes on the left, Gen-4.5 video nodes in the middle, Stitch + audio on the right. Leave 80 to 120 pixels of whitespace between any two nodes.
ii.   **Open Runway, save the workflow.** Name it `<Project_Name>` matching `ACTIVE_PROJECTS/<Name>/`.
iii.  **Place every node first, in clean positions.** Right-click on empty canvas at the intended position to spawn the node there. If a new node lands on top of an existing one, drag it (by the top-middle of the title bar) before doing anything else.
iv.   **Wire every connection before populating any Text.** This is the critical pivot from the old approach. Reverse-drag from each input to its source. Verify every edge via `inspect_canvas.js`.
v.    **Verify every ∞ toggle ON.** Use the audit script: query every generation node's `input[type="checkbox"]` and confirm `checked === true`. If any are off, click them via MCP at the scaled toggle coordinates.
vi.   **Populate Text nodes** via `form_input` or the native textarea value setter.
vii.  **Generate in batches of 2.** Runway will not let you queue more than 2 video clips at once. Wait for one to finish before triggering the next.
viii. **Frame-by-frame scrub each clip** as it finishes. Do not start the next batch until the previous ones pass QA.

### Layout template (canonical 30s build)

Joseph's reference layout, 2026-05-20:

```
Column 1: Text prompts (one per row, vertical stack)
Column 2: NBP reference images (Ref A near top, Ref B middle, Ref C bottom)
Column 3: Per-clip Text prompts (vertical stack, one per clip row)
Column 4: 6 Gen-4.5 video clips (vertical stack, Clip 01 top → Clip 06 bottom)
Column 5: Stitch (top) + Add Audio (below Stitch)
Bottom-right corner: Text VO + Text to Speech (audio chain)

Wires fan from each clip's video output into Stitch inputs, diagonally
from middle-column clips to far-right Stitch. TTS audio out runs to
Add Audio audio input. Stitch video out runs to Add Audio video input.
```

The clean version of this layout looks like:

```
[Text 01]─[NBP-A]──[Text Clip 01]─[Clip 01]──┐
                  ─[Text Clip 02]─[Clip 02]──┤
[Text Ref B]─[NBP-B]─[Text Clip 03]─[Clip 03]┼──[Stitch]──[Add Audio]
                  ─[Text Clip 04]─[Clip 04]──┤              │
                  ─[Text Clip 05]─[Clip 05]──┤              │
[Text Ref C]─[NBP-C]─[Text Clip 06]─[Clip 06]┘              │
                                                            │
[Text VO]──[TTS]────────────────────────────────────────────┘
```

**Spacing convention:** 150px horizontal between connected nodes, 150px vertical between rows. Each clip row has its own dedicated Text node on the left of its Gen-4.5 video node.

**Why this layout:**
i.   Left-to-right flow matches Runway's data direction (inputs on left, outputs on right).
ii.  Clips stacked vertically make the time order obvious top-to-bottom.
iii. Stitch + Add Audio at the far right makes the final output node the visual endpoint.
iv.  Audio chain at the bottom right keeps the video chain visually clean.
v.   Every wire runs in a straight or gently curved path with no crossovers in the middle.

### The pre-flight checklist before any Run

```
[ ] Every node placed and not stacking
[ ] Every Text node populated with the right prompt
[ ] Every wire from input to source confirmed via `inspect_canvas.js`
[ ] Every generation node's ∞ checkbox is checked === true
[ ] Active generations ≤ 2 (Runway concurrency limit)
[ ] Browser zoom level appropriate (zoom in for precise clicks on small targets)
[ ] Settings menu on each node reviewed if non-default duration / aspect ratio needed
```

If ANY box is unchecked, fix it before pressing Run. Never press "Run all" unless every upstream node either has the correct prompt or has a cached output you do not want regenerated.

---

## The Standard Pipeline (per project)

### Step 1. Intake and brief
- `/format-30s-commercial` (or whichever format skill fits) creates the scaffold.
- Save to `ACTIVE_PROJECTS/<Name>/01_brief.md`.

### Step 2. Script and shot list
- Apply the format's timing rules and the Anti-AI Laws.
- Save to `02_script.md` and `03_shot_list.md`.

### Step 3. Generate Runway prompts
- One of `/style-01` through `/style-05` produces six prompts that conform
  to all 16 Anti-AI Laws and append the style token verbatim.
- Save to `04_runway_prompts.md`.

### Step 4. Workflow plan and QA checklist
- The matching template in `TEMPLATES/` produces the Runway node build plan
  and the pre-generation QA checklist.
- Save to `05_workflow_plan.md` and `06_qa_checklist.md`.

### Step 5. Run the pipeline
- `/runway-full-pipeline <project-name>` does the rest:
  - Opens Runway, creates a new Workflow named after the project.
  - Generates the 1-3 reference images on Nano Banana Pro.
  - Generates 6 Gen-4.5 video clips wired to the references.
  - Adds Stitch node, TTS node, **Text-to-SFX node**, and Add Audio (multi-layer).
  - Saves progress to `SESSION-RESUME.md` after each step.
- Or run the four sub-skills individually if you want to inspect between steps.

### Step 5b. Audio composition (multi-layer when the video calls for it)

**Purpose:** make the commercial sound professionally made and real, not AI-generated. A bare TTS over silent video reads as AI immediately. Layered foley, ambience, and a music bed lift the production into broadcast quality.

**Use TTS + Text-to-SFX together when the build calls for:**
- A scripted commercial with narration over silent visuals (default for broadcast cuts).
- A documentary cut where natural ambience and foley need to fill the room (Style 03).
- Any client deliverable headed to LinkedIn, YouTube, broadcast, or paid social.

**Use TTS alone (no SFX) when:**
- The video is dialogue-heavy and the visuals carry the atmosphere on their own.
- A licensed music track will be added in post (then skip Text-to-SFX and let the editor drop the music in their NLE).
- Quick internal-review cuts where post-production sound design isn't needed yet.

**Use Text-to-SFX alone (no TTS) when:**
- The video is purely visual with on-screen captions doing the talking (silent-first LinkedIn cuts).
- A mood reel or product demo that needs ambient texture but no narration.

**Skip both when:**
- Joseph or Owner has flagged that audio will be handled entirely in the editor.
- The deliverable is a frame-only export (e.g., for thumbnails or static social).

When using multi-layer audio, the chain is:

i.    **Text to Speech (TTS, eleven-text-to-speech-2)** — narration / voiceover. Right-click → `Audio > Text to Speech`. Wire a Text node holding the VO copy to its `text-target`. Voice and pace are set inside the node's settings menu (gear icon, top-right of node).

ii.   **Text to SFX** — music bed, room tone, foley, synth swell, mechanical ticks, pen-on-paper, ambient atmosphere. Right-click → `Audio > Text to SFX`. Wire a Text node holding the SFX description (e.g., "soft brass lamp click, mechanical clock tick, fountain pen mark on heavy paper, room tone office at golden hour, low synth swell") to its `text-target`. Set duration in the settings menu to match the final video length.

iii.  **Add Audio** combines video + multiple audio layers. Right-click → `Video > Add Audio`. Wire:
        - Stitch video output → Add Audio `video-target`
        - TTS audio output → Add Audio `audio-target[0]`
        - Text-to-SFX audio output → Add Audio `audio-target[1]`
      Add Audio grows additional input slots as you wire more audio sources, similar to how Stitch grows video inputs.

iv.   **Optional third audio layer** if you want a separate music track. Chain another Add Audio downstream of the first, wiring the previous Add Audio's video output to the new one's video input plus the music source.

The full audio chain for a 30s video:
```
Text(VO) → TTS → audio[0]
Text(SFX) → Text-to-SFX → audio[1]
Stitch (6 video clips combined) → video
                       ↓
                   Add Audio → final master video
```

Default SFX for Style 02 builds: "sparse solo piano motif in D minor, sustained navy synth pad, slow build, no drums, restrained, premium cinematic, with subtle foley accents: soft brass lamp click at 0:00, mechanical clock tick at 0:08, fountain pen mark on heavy paper at 0:18, low synth swell into the CTA hold at 0:27".

### Step 6. Frame-by-frame QA
- Scrub the final video for: text gibberish (Law 13), silhouettes (Law 14),
  symbol errors (Law 16), wordmark rendering (Law 15).
- If any clip fails, regenerate just that clip.

### Step 7. Handoff
- `07_handoff_to_runway.md` documents the exact post-production sequence
  (caption burn-in, end-card composite, three-crop export, audio mix).
- Owner approval gate before any public release.

---

## Critical Runway UI Patterns (the rules Claude must follow every session)

### Node placement
**Best:** right-click on the empty canvas where you want the node, pick from
context menu. The node spawns where you clicked.
**Fallback:** click the `+` button, pick a node, then drag the new node by the
**top-middle of the title bar** to clear space.

### Wiring
**Drag wires from input dot to output dot (reverse direction).** Forward drags
frequently fail over Chrome MCP. The MCP scales mouse coordinates by the ratio
`browserInnerWidth / screenshotWidth` (typically 1.224x).

When using `mcp__Claude_in_Chrome__computer left_click_drag`:
- Get the actual browser pixel coordinates of the two handles via
  `scripts/inspect_canvas.js` or `scripts/get_handle_coords.js`.
- Divide by the active scale factor before passing to MCP.

If MCP drag still fails, fall back to `scripts/wire_handles.js` which dispatches
PointerEvents directly on the DOM. Verify the new edge appeared via
`inspect_canvas.js`.

### Run button
Always use the **per-node Run button** rather than the top-bar "Run all"
unless every node is freshly configured. Run all will re-run cached upstream
nodes, which can clobber a good reference image if its source Text node
has been edited.

To click Run reliably without coordinate guessing:
```javascript
// in javascript_tool
const node = document.querySelector(`[data-id="<NODE_UUID>"]`);
node.querySelectorAll("button").forEach(b => {
  if (b.textContent.trim() === "Run") b.click();
});
```

### Infinity (∞) toggle per node
Off by default. Toggle ON before pressing Run. It draws from the premium plan
credit pool. The toggle is the small switch at the lower-left of every
generation node.

### Text node prompt entry
Use `mcp__Claude_in_Chrome__form_input` against the Text node's textarea ref,
not on-canvas typing. The textarea ref can be found via:
```
find query: "empty Text node textarea with placeholder Type a prompt"
```
Beware: refs renumber between `find` calls in the same session. Re-find
before each operation.

### Layout convention
Left-to-right per row, one row per clip. Suppliers (text, references) on the
left. Consumers (video, stitch) on the right. For 6-clip 30s commercials,
arrange in 3 rows of 2 columns or 6 rows of single columns.

---

## Model URLs and Settings

| Surface | Path inside Runway Workflows |
|---|---|
| Workflows index | `/video-tools/teams/<team>/ai-tools/workflows` |
| Workflow editor | `/video-tools/teams/<team>/ai-tools/workflows/<id>/edit` |
| Nano Banana Pro | added via right-click → `Image > Nano Banana Pro` |
| Gen-4.5 Text+Image to Video | added via right-click → `Video > Gen-4.5 (Text+Image to Video)` |
| Gen-4.5 Text to Video | added via right-click → `Video > Gen-4.5 (Text to Video)` |
| Stitch | search picker for "Stitch" |
| Text to Speech | search picker for "Text to Speech" or category Audio |
| Add Audio | search picker for "Add Audio" |

### React Flow node type strings (for `find_node_by_type.js`)

| Type string | Node |
|---|---|
| `text` | Text input node |
| `gemini-image-3-pro` | Nano Banana Pro |
| `gen4_5-image-to-video` | Gen-4.5 Text+Image to Video |
| `gen4_5-text-to-video` | Gen-4.5 Text to Video |
| `stitch` | Stitch |
| `text-to-speech` | TTS |
| `add-audio` | Add Audio |

### Handle naming convention

```
1-<nodeId>-<paramName>-target   (input dot)
1-<nodeId>-<paramName>-source   (output dot)
```

Common parameter names:
- `text_prompt` — required prompt input on Gen-4.5, NBP, Stitch
- `start_frame` — Gen-4.5's First Video Frame input (the image-to-video seed)
- `reference_images[0]` — NBP's optional image-conditioned input
- `image` — NBP's image output
- `video` — Gen-4.5's video output

### Edge id pattern
```
xy-edge__<sourceNodeId><sourceParam>-<targetNodeId><targetParam>
```

---

## Default settings

### Default luxury / premium (Style 02)
- Model: Nano Banana Pro for references, Gen-4.5 Text+Image to Video for clips
- Aspect ratio: 9:16 vertical (primary cut for LinkedIn mobile)
- Clip duration: 5 seconds (under the Law 9 ceiling of 6)
- Style token (appended verbatim to every prompt):
  `shot on ARRI Alexa Mini LF, 50mm Master Prime, warm tungsten key light left side, deep navy ambient fill, premium cinematic grade with soft gold accent highlights, fine 35mm grain structure`
- ∞ toggle: ON on every generation node

### Default Corporate Cinematic (Style 01)
For B2B, legal, finance, and professional services builds.
- Same models
- Aspect ratio depends on platform (16:9 for trade deliverables, 9:16 for social)
- Style token:
  `shot on ARRI Alexa Mini LF, 32mm Cooke S4 lens, T2.0, warm tungsten practical window light from the left, cinematic color grade with deep shadows and controlled highlights, fine ARRI sensor grain`

---

## Workflow Rules (always)

i.    **Build the production package first** (brief, script, shot list, prompts,
      workflow plan, QA checklist) before touching Runway.
ii.   **Pre-generation QA must pass** all 20 items in `06_qa_checklist.md`.
iii.  **No invented credits, stats, or claims.** Every number or claim in a deliverable must be sourced and approved. Flag uncertainty rather than fabricating.
iv.   **No em-dashes** anywhere in any deliverable (voice rule).
v.    **Save progress to `SESSION-RESUME.md`** after each clip generation so a
      crashed session can pick up where it left off.
vi.   **Ask Owner for approval** before any LinkedIn upload.
vii.  **Frame-by-frame scrub** before exporting from Runway. Look for text
      gibberish, silhouette artifacts, symbol errors (per Laws 13, 14, 16).
viii. **Post-production happens outside Runway** in the editor. Caption
      burn-in, end-card composite, and three-crop export are not in scope
      for `/runway-full-pipeline`.

---

## SESSION-RESUME.md

A live status file per active project, written to
`ACTIVE_PROJECTS/<Name>/SESSION-RESUME.md`. Updated by every automation
skill after each generation. If a session crashes mid-build, Claude reads
this file first to know where to pick up.

See `TEMPLATES/SESSION-RESUME.template.md` for the format.

---

## Skills Reference

See the `SKILLS/runway/` directory for full skill definitions. The four core
automation skills are:

### `/runway-full-pipeline`
Orchestrates the entire build. Reads `04_runway_prompts.md`, opens Runway,
generates references, builds clips, stitches, adds audio. Writes progress to
`SESSION-RESUME.md` continuously.

### `/runway-image-auto`
Generates one reference image on Nano Banana Pro inside the current Runway
Workflow. Takes a prompt and an optional first-frame reference. Returns the
new node's id and image output handle.

### `/runway-video-auto`
Generates one Gen-4.5 Text+Image to Video clip. Takes a prompt, a first-frame
image source (NBP node id or another clip's video output), and runs the clip.
Returns the new node's id and video output handle.

### `/runway-stitch-auto`
Wires N clip video outputs into a Stitch node, then adds Text to Speech and
Add Audio nodes. Returns the final Add Audio output handle.

---

## The Core Idea

`CLAUDE.md` defines the rules. `SKILLS/` defines the expertise. The Chrome MCP
gives Claude hands. The `TOOLKIT/scripts/` gives Claude reliable patterns for
the parts of Runway that don't behave well over Chrome MCP.

Instead of:

> Idea → write brief → write script → write prompts → open Runway → place nodes → wire nodes → type prompts → toggle infinity → press Run → wait → repeat 6 times → place Stitch → wire → place TTS → wire → place Add Audio →