---
name: runway-video-auto
description: Automates Gen-4.5 Text+Image to Video clip generation inside a Runway Workflow via the Claude in Chrome MCP. Adds the Gen-4.5 node, adds a Text node with the clip prompt, wires Prompt and First Video Frame inputs, toggles ∞ ON, presses Run, waits for the clip, and returns the new node's id and video-source handle. Use for each 5-second clip in a multi-clip video.
---

# Skill: runway-video-auto

## When to invoke

User says any of:
- "generate clip 02 on Runway"
- "make the brass clock video clip"
- "add a Gen-4.5 video node and run it"

Also invoked internally by `/runway-full-pipeline` once per clip in
`04_runway_prompts.md`.

## Inputs

Required:
- `prompt` — the full video prompt text. Must include the Style token verbatim
  per the project's locked style system. Must satisfy all 16 Anti-AI Laws.
- `first_frame_image_source_handle_id` — the `image-source` handle id of the
  image node (NBP or other) whose output seeds the clip's First Video Frame.

Optional:
- `placement` — `{x, y}` browser pixel position where the new Gen-4.5 node
  should spawn. Defaults to the next empty canvas slot in row order.
- `duration_seconds` — 5 (default) or up to 6 (Law 9 ceiling).

## Pre-flight checks

i.    Workflow open in Runway.
ii.   Browser connected.
iii.  Credit balance covers at least 5 credits per clip at standard quality.
iv.   Prompt satisfies all 16 Anti-AI Laws:
      - Image-to-video for any human subject (Law 1)
      - One light source named (Law 2)
      - Style token as final sentence (Law 3)
      - Camera body + lens (Law 4)
      - Film grain (Law 5)
      - Medium shot or tighter (Law 6)
      - No hands close to frame (Law 7)
      - Motivated camera (Law 8)
      - 6 seconds max (Law 9)
      - One action (Law 10)
      - No AI cliches (Law 11)
      - Physics described (Law 12)
      - No readable text (Law 13)
      - No silhouetted humans (Law 14)
      - All stats / wordmarks / URLs in post (Law 15)
      - No symbols (Law 16)
v.    No em-dash anywhere in prompt.

## Procedure

### 1. Compute placement
Same logic as `runway-image-auto`. Pick the next empty canvas slot.

### 2. Right-click placement
Open the picker at the desired canvas position via right-click.

### 3. Pick the Gen-4.5 model
Click Video category, then click "Gen-4.5 (Text+Image to Video)."

### 4. Add the Text node
Right-click on empty canvas immediately to the left of the new Gen-4.5 node.
Pick `Text > Text`.

### 5. Populate the Text node
Use `find` for the new empty textarea, then `form_input` to set the full
clip prompt as its value.

### 6. Wire Text node → Gen-4.5 Prompt
Run `inspect_canvas.js`. Identify the two handles. Reverse-drag from Gen-4.5's
`text_prompt-target` to the Text node's `prompt-source`, scaled coords.

Verify edge appeared via `inspect_canvas.js`.

### 7. Wire image source → Gen-4.5 First Video Frame
Locate the source handle by id (passed in as input). Reverse-drag from
Gen-4.5's `start_frame-target` to that source handle.

Verify edge appeared.

### 8. Toggle ∞ ON
Click the toggle at lower-left of the Gen-4.5 node. Confirm via screenshot.

### 9. (Optional) Set duration
If `duration_seconds` is provided and not 5, open the node's settings panel
and set the duration. Note: Gen-4.5 defaults to 5s which is the safe choice.

### 10. Press Run via DOM
```javascript
const node = document.querySelector(`[data-id="<GEN45_UUID>"]`);
node.querySelectorAll("button").forEach(b => {
  if (b.textContent.trim() === "Run") b.click();
});
```

### 11. Wait for completion
Poll every 10-15 seconds. Gen-4.5 clip generation: typically 60-90 seconds
for 5s at standard quality. Maximum reasonable wait: 3 minutes.

### 12. Verify the clip
Click play on the rendered video preview. Watch the full 5 seconds.

Check for:
- Camera movement matches prompt (push-in, arc, orbit, etc.)
- No artifacts: no text gibberish, no anatomy errors, no symbol distortion
- First frame matches the wired reference image
- Style consistency with previous clips

If the clip fails QA, report to user with the screenshot and offer to
regenerate.

### 13. Return values
```json
{
  "node_id": "<uuid>",
  "video_source_handle_id": "1-<uuid>-video-source",
  "text_node_id": "<uuid>",
  "credits_spent": 4
}
```

### 14. Update RUN_STATE.md (or SESSION-RESUME.md if DRIVE_MODE=manual-handoff)
Update the WAVE_2 row for this clip with the new node id, start/end timestamps,
and status = `rendered`. If DRIVE_MODE = `manual-handoff`, update
SESSION-RESUME.md instead.

Also call `runway-timing-memory.record('gen-4.5_5s_standard', null, actual_duration)`
(or `gen-4.5_10s_standard` for 10-second clips) so the persistent driver's
next-check-in scheduler learns from real data.

## Failure modes and fixes

Same as `runway-image-auto`, plus:

| Symptom | Likely cause | Fix |
|---|---|---|
| Run does nothing, no progress bar | First Video Frame unwired | Verify via inspect, re-wire if missing |
| Run shows (i) info badge | Required input missing | Same as above |
| Clip generates but face is glitched | Image-to-video chain broke | Verify the wired image source matches the prompt's subject |
| Clip has text gibberish in frame | Prompt described readable text | Rewrite prompt removing Law 13 violation |
| Clip is 6+ seconds | Duration not set | Open settings panel, change to 5s |

## Output format

```
[AUTO]

Clip <N> generated: <uuid>
Duration: 5 seconds
Camera move: <description>
First frame: matches <reference image name>
Artifacts found: <none / list>
Credits spent: 4
Video-source handle: 1-<uuid>-video-source
Next: pass this handle id to /runway-stitch-auto as input <N>
```

## Related skills
- `/runway-image-auto` — produces the image source handle this skill consumes
- `/runway-stitch-auto` — consumes this skill's video-source handle
- `/runway-full-pipeline` — orchestrates 6+ invocations of this skill
- `/style-02-luxury-premium` — generates the prompt this skill consumes
