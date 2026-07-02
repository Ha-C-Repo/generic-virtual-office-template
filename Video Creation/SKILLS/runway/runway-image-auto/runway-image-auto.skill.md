---
name: runway-image-auto
description: Automates Nano Banana Pro reference image generation inside a Runway Workflow via the Claude in Chrome MCP. Adds the NBP node, adds a Text node with the prompt, wires them, toggles ∞ ON, presses Run, waits for the image, and returns the new node's id and image-source handle id. Use when a project needs a reference image that downstream Gen-4.5 clips will use as their First Video Frame.
---

# Skill: runway-image-auto

## When to invoke

User says any of:
- "generate reference A on Runway"
- "make the desk reference image"
- "add a Nano Banana Pro node and run it"
- "I need a fresh first-frame image for this scene"

Also invoked internally by `/runway-full-pipeline` once per reference image
in `04_runway_prompts.md`.

## Inputs

Required:
- `prompt` — the full image prompt text. Must include the Style token verbatim
  per the project's locked style system.

Optional:
- `placement` — `{x, y}` browser pixel position where the new NBP node should
  spawn. Defaults to the next empty canvas slot in row order.
- `reference_image_node_id` — UUID of an existing image node to wire to NBP's
  `reference_images[0]` input for image-conditioned generation.

## Pre-flight checks

i.    Confirm a Workflow is open in Runway (URL contains `/workflows/<uuid>/edit`).
ii.   Confirm browser is connected via `list_connected_browsers`.
iii.  Confirm credit balance covers at least 5 credits (NBP costs ~4).
iv.   Confirm the prompt does not contain any em-dash (voice rule).
v.    Confirm the prompt does not violate Law 13 (no readable text in frame)
      or Law 14 (no silhouetted humans).

## Procedure

### 1. Compute placement coordinates
- If `placement` is provided, use it.
- Otherwise, query existing nodes via `inspect_canvas.js` and pick the next
  empty slot. Standard rows are at y = 393, 542, 691, etc., spaced ~150px apart.
  Standard columns at x = 473, 612, 765, 918, etc., spaced ~150px apart.

### 2. Right-click placement
Compute the MCP input coordinates: `(actual_x / scale, actual_y / scale)`
where `scale = window.innerWidth / screenshot_width` (typically 1.224x).

```
mcp__Claude_in_Chrome__computer right_click at scaled coords
```

### 3. Pick Nano Banana Pro from the picker
Click the Image category, then click "Nano Banana Pro." Confirm via screenshot
that the new node spawned at the right-click position.

### 4. Add Text node
Right-click on the empty canvas to the LEFT of the new NBP node (typically
~150px to the left at the same y). Click Text category, then "Text" plain option.

### 5. Populate the Text node
Use `find` to locate the new empty textarea (placeholder "Type a prompt").
Then use `form_input` to set its value to the full prompt string.

### 6. Wire Text → NBP Prompt
Run `inspect_canvas.js` to get exact pixel coordinates of:
- Text node `prompt-source` handle
- NBP node `text_prompt-target` handle

Use `mcp__Claude_in_Chrome__computer left_click_drag` with REVERSE direction
(input dot to output dot), scaling coords down by the active scale factor.

Verify via `inspect_canvas.js` that the new edge `xy-edge__<text>prompt-<nbp>text_prompt`
appears in the edges list.

### 7. (Optional) Wire reference image input
If `reference_image_node_id` was provided, do the same drag from that node's
`image-source` to NBP's `reference_images[0]-target`.

### 8. Toggle ∞ ON
Inside the NBP node, find the ∞ toggle (small switch at lower-left). Click it.
Verify via screenshot that the toggle slider moves to the right (blue/active).

### 9. Press Run via DOM
```javascript
// in javascript_tool
const node = document.querySelector(`[data-id="<NBP_UUID>"]`);
node.querySelectorAll("button").forEach(b => {
  if (b.textContent.trim() === "Run") b.click();
});
```

### 10. Wait for completion
Poll the node every 10-15 seconds. Progress shows as "0%" through "100%."
Typical NBP generation: 15-30 seconds. Maximum reasonable wait: 90 seconds.

### 11. Verify the image
Screenshot the completed node. Confirm:
- Image rendered (not blank or error)
- Image is on-brand for the project's style system
- No people, no faces, no readable text, no logos (Law 13, 14, 15)

If the image fails QA, report to user with the screenshot and offer to
regenerate (which costs another ~4 credits).

### 12. Return values
On success, return:
```json
{
  "node_id": "<uuid>",
  "image_source_handle_id": "1-<uuid>-image-source",
  "text_node_id": "<uuid>",
  "credits_spent": 4
}
```

### 13. Update RUN_STATE.md (or SESSION-RESUME.md if DRIVE_MODE=manual-handoff)
Update the WAVE_1 row for this NBP with the new node id, start/end timestamps,
and status = `rendered`. If DRIVE_MODE = `manual-handoff` (a real human-required
blocker per CLAUDE.md PERSISTENT EXECUTION DISCIPLINE), update SESSION-RESUME.md
instead.

Also call `runway-timing-memory.record('nano-banana-pro_2K', null, actual_duration)`
so the persistent driver's next-check-in scheduler learns from real data.

## Failure modes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Right-click does nothing | Click landed on an existing node | Move farther into empty canvas |
| Picker closes before pick | Stray click outside picker | Re-right-click and try again |
| Text node hidden behind NBP | Node stacking from `+` button path | Drag the new node by its title bar top-middle |
| `form_input` reports unexpected previous value | Element ref renumbered | Re-run `find` and retry on new ref |
| Wire didn't form | Drag missed handle by a pixel | Use `wire_handles.js` as fallback |
| Generation stalls at 0% | ∞ toggle was off | Toggle it on, retry Run |
| Image is off-brand | Prompt missing style token | Verify Step 1 prompt content, regenerate |
| Account balance insufficient | Too many runs this month | Stop and surface to Joseph |

## Output format

The skill returns a Mode A status to the parent context:

```
[AUTO]

NBP node added: <uuid>
Image rendered: <yes/no, with one-line description of visual>
Credits spent: 4
Image-source handle: 1-<uuid>-image-source
Next: pass this handle id to /runway-video-auto as the First Video Frame source
```

## Related skills
- `/runway-video-auto` — consumes this skill's output handle
- `/runway-full-pipeline` — orchestrates multiple invocations of this skill
- `/style-02-luxury-premium` consumes the prompt this skill produces (luxury / premium)
- `/style-01-corporate-cinematic` consumes th