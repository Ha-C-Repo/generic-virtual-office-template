# RUNWAY MCP TOOLKIT
## Driving Runway Workflows via Chrome MCP

*Field-tested patterns from the a prior 30s LinkedIn build, 2026-05-20.
Read this before attempting another Runway build via Chrome MCP.*

---

## The mental model

Runway Workflows is built on **React Flow**, a node-graph library. Every node, handle (connection dot), and edge (wire) has a stable DOM id. The visible canvas is a transformed view of an underlying coordinate system. The Chrome MCP sends clicks at viewport pixel coordinates, but Runway's drag handlers can be picky about exact positions on small targets.

The trick to driving this UI through MCP: **stop guessing coordinates from screenshots. Query the DOM for the exact pixel positions, then click those numbers.**

---

## The Run-Order Rule (NEVER Run all on a partially-cached canvas)

**Run all is BANNED on any canvas with rendered nodes.** Pressing Run all restarts every node, burns credits regenerating cached clips, and emits "node not yet run successfully" errors mid-chain. Run nodes one at a time in dependency order. Use the per-node Run button (click via DOM lookup):

```javascript
const node = document.querySelector(`[data-id="<NODE_UUID>"]`);
node.querySelectorAll("button").forEach(b => {
  if (b.textContent.trim() === "Run") b.click();
});
```

Standard 30s 6-clip sequence:
i.    Run NBP-A, wait for image.
ii.   Run Clip 01, Run Clip 02 (concurrent limit is 2), wait for both.
iii.  Run NBP-B, wait.
iv.   Run Clip 03, Run Clip 04, wait both.
v.    Run NBP-C, wait.
vi.   Run Clip 05, Run Clip 06, wait both.
vii.  Run TTS, wait.
viii. Run Stitch, wait.
ix.   Run Add Audio, wait. Final master complete.

Do not restart cached outputs. Upstream outputs feed forward; only press Run on the specific downstream node whose output you need to refresh.

---

## The Layout-First Build Rule (LFB)

**Joseph's standing rule:** plan the canvas, place every node, wire every edge, verify every ∞ toggle — THEN populate Text and run.

Build sequence:
i.    Plan layout (rows and columns, 150px spacing minimum).
ii.   Place every node with right-click on empty canvas at the intended position.
iii.  Drag any stacked node to clear space immediately (drag by top-middle of title bar).
iv.   Wire every connection (reverse-drag from input to source). Verify edges via `inspect_canvas.js`.
v.    **Toggle ∞ ON every node the moment you place it.** Don't wait for the audit. ∞ is part of the placement step, not a separate cleanup. Then do an additional FINAL ∞ sweep before any Run. Audit script:
```javascript
document.querySelectorAll('.react-flow__node').forEach(n => {
  const id = n.getAttribute('data-id');
  const cb = n.querySelector('input[type="checkbox"]');
  if (cb) console.log(id, cb.checked);
});
```
vi.   Populate Text inputs.
vii.  Open each node's settings menu (gear icon top-right) and verify duration, aspect ratio, model variant.
viii. Generate in batches of 2 (Runway concurrency limit). Wait for previous batch to finish.
ix.   Frame-by-frame scrub each clip as it lands.

The ∞ toggle is an `<input type="checkbox">` inside `.Switch__SwitchWrapper-kxfoNw`. JS dispatch does NOT work — must use MCP click at the scaled wrapper coordinates:
```javascript
const cb = node.querySelector('input[type="checkbox"]');
const r = cb.closest('.Switch__SwitchWrapper-kxfoNw').getBoundingClientRect();
const scale = window.innerWidth / screenshotWidth;
// then MCP left_click at (r.x + r.width/2)/scale, (r.y + r.height/2)/scale
```

## Canvas layout pattern (canonical, Joseph 2026-05-20)

Lay out the canvas as columns reading left to right:

i.    Column 1: Reference image Text prompts (one per NBP source).
ii.   Column 2: NBP reference image nodes (one per source).
iii.  Column 3: Per-clip Text prompts (one per Gen-4.5 video clip, vertical stack).
iv.   Column 4: Gen-4.5 video clips (vertical stack, time order top to bottom: Clip 01 at top, Clip 06 at bottom).
v.    Column 5: Stitch (top), Add Audio (below Stitch).
vi.   Bottom-right corner: Text VO + Text-to-Speech, wired to Add Audio.

Spacing: 150px horizontal between connected columns, 150px vertical between clip rows.

The wires fan from each clip's video output diagonally into Stitch's input[N] slot. TTS audio runs to Add Audio audio input. Stitch video runs to Add Audio video input.

Every wire should follow a straight or gently curved path with no crossovers through the middle of the canvas. If wires cross or nodes overlap, the layout is wrong; drag the offending node to clear space.

---

## Use zoom and node settings deliberately

- **Zoom in** before clicking small targets (∞ toggle is 11x5 pixels at default zoom; useless). The bottom toolbar has a zoom-in button at fixed pixel position. Three clicks zooms in to a workable level.
- **Zoom out** when you need a layout overview or to drag-pan across the canvas.
- **Every node has a settings menu** (gear icon top-right of node header). Open it to set duration, aspect ratio, model variant, seed. Defaults are usually fine but verify before generating expensive clips.

## Three things that bite you (and the fix for each)

### 1. New nodes spawn at canvas center and stack behind existing nodes
**Best fix:** right-click on the empty canvas where you want the node, then pick the node type from the context menu. The node spawns at your right-click position.
**Fallback:** drag the new node by the **top-middle of the title bar** to clear space (drag handle lives there; clicking elsewhere on the title may hit an icon).

### 2. Coordinate scaling between MCP input and actual browser pixels
The Chrome MCP scales the coordinates you pass by `window.innerWidth / screenshot_width`. If the browser is at 1920px and screenshots come at 1568px, the scale factor is **1.224x**.

To target an element at actual browser pixel `(X, Y)`, send MCP input `(X / scale, Y / scale)`.

Always query the scale at the start of a session:
```javascript
window.devicePixelRatio
window.innerWidth
window.innerHeight
```
Compare to screenshot dimensions to get the active scale.

### 3. Drag wires from input dot to output dot (reverse direction)
Forward drags (source output → target input) frequently fail to register.
Reverse drags (target input → source output) work reliably.
Same applies to wiring from JavaScript-dispatched PointerEvents.

---

## The handle naming scheme (React Flow ids)

**Node ids** are UUIDs like `b469f38f-32b1-41d0-9ebf-2a0ce701f8d8`.

**Handle ids** follow this pattern:
```
1-{nodeId}-{paramName}-target      (input)
1-{nodeId}-{paramName}-source      (output)
```

For example:
- `1-b469f38f-...-image-source` → Nano Banana Pro image output
- `1-ea4b0bab-...-start_frame-target` → Gen-4.5 First Video Frame input
- `1-ea4b0bab-...-text_prompt-target` → Gen-4.5 Prompt input
- `1-ea4b0bab-...-video-source` → Gen-4.5 Video output

**Edge ids** (wires) follow:
```
xy-edge__{sourceNodeId}{sourceParam}-{targetNodeId}{targetParam}
```

---

## The standard build sequence

For a multi-clip video with consistent first frame:

### Step 1. Place reference image node
Right-click empty canvas → `Image > Nano Banana Pro`. Wire a Text node to its Prompt input. ∞ toggle ON. Run. Wait for image.

### Step 2. For each clip
i.   Right-click empty canvas in a clear row position → `Video > Gen-4.5 Text+Image to Video`.
ii.  Right-click empty canvas next to it → `Text > Text`. Fill via `form_input` on its textarea ref.
iii. Wire Text → Clip Prompt. Wire reference image → Clip First Video Frame.
iv.  ∞ toggle ON on the Gen-4.5 node.
v.   Run.

### Step 3. Stitch
Right-click → search picker for `Stitch`. Wire each clip's video output into Stitch inputs in time order.

### Step 4. Audio
Right-click → `Audio > Text to Speech`. Wire VO text node to it.
Right-click → `Video > Add Audio` (or similar). Wire Stitch video output and TTS audio output into it.

### Step 5. Run all and scrub
Press Run all at the top. Wait for full chain. Scrub the final output frame-by-frame.

---

## Scripts

See `scripts/` directory:
- `inspect_canvas.js` — dump every node, handle, and edge currently on the canvas
- `get_handle_coords.js` — return precise pixel coordinates for two named handles (for use with MCP drag)
- `wire_handles.js` — dispatch PointerEvents to programmatically create a wire (use as fallback if MCP drag fails)
- `find_node_by_type.js` — locate nodes by their type string (e.g., `gen4_5-image-to-video`)

---

## What goes wrong and what to do about it

| Symptom | Diagnosis | Fix |
|---|---|---|
| Drag does nothing | Coords off by scale factor | Divide actual browser pixel by 1.224 |
| Node hidden, refs stale | Element refs renumber between find calls | Re-run find before each operation |
| Wire didn't form | Drag landed near handle but missed | Use `inspect_canvas.js` to get exact handle pixel center |
| Run button shows (i) badge | Required input unwired | Query edges, find missing target |
| Generation stalls at 0% | ∞ toggle OFF | Click toggle, retry Run |
| New node hidden behind existing | Center-spawn collision | Right-click empty space to place, or drag by top-middle |
| `Run All` clobbers a cached image | Upstream Text node has wrong prompt | Restore Text node, or Run individual node only |

---

## Anti-AI Laws applied to every Runway prompt

Project rule from `CLAUDE.md`. Every prompt must satisfy all 16:
i.     Image-to-video for any clip with a human subject.
ii.    One light source, named, directional.
iii.   Style token copy-pasted verbatim as the final sentence.
iv.    Specific camera body and lens.
v.     Film grain in every prompt.
vi.    Medium shot or tighter; no wide shots with small figures.
vii.   No hands described close to frame.
viii.  Camera is motivated (start, end, speed).
ix.    Max 6 seconds per clip.
x.     One action per clip.
xi.    No AI cliches (aerial city, handshake, person at laptop).
xii.   Physics described for any interaction.
xiii.  No readable text or documents in frame.
xiv.   No silhouetted or middle-distance human figures.
xv.    All stats, lower-thirds, wordmarks, URLs, phone numbers composited in post.
xvi.   Spell out symbols (write "three cents" not "3¢").

---

## Style tokens (paste verbatim into the prompt's final sentence)

**Style 01 (Corporate Cinematic, B2B, legal, finance, professional services):** `shot on ARRI Alexa Mini LF, 32mm Cooke S4 lens, T2.0, warm tungsten practical window light from the left, cinematic color grade with deep shadows and controlled highlights, fine ARRI sensor grain`

**Style 02 (luxury / premium):** `shot on ARRI Alexa Mini LF, 50mm Master Prime, warm tungsten key light left side, deep navy ambient fill, premium cinematic grade with soft gold accent highlights, fine 35mm grain structure`

**Style 03 (documentary):** `shot on Sony FX3, 35mm equivalent, natural available window light, handheld with slight organic motion, raw indie film aesthetic, natural color temperature, fine grain`

**Style 04 (bold launch):** `shot on RED Komodo-X, 24mm Sigma Art lens, high contrast color grade, bold saturation, commercial advertising aesthetic, ultra-sharp`

**Style 05 (product):** `studio seamless background, three-point studio lighting, macro lens detail, commercial product photography aesthetic, 8K, white background`

---

## Credit economics (current Runway Unlimited tier)

| Operation | Approx credits |
|---|---|
| Nano Banana Pro image | 4 |
| Gen-4.5 Text+Image to Video 5s standard | 4 |
| Gen-4.5 Text+Image to Video 5s Final Quality | ~10 |
| Stitch | 0 |
| Text to Speech 30s | ~5 |
| Add Audio | 0 |
| 4K upscale per second | 2 |

A 30s 6-clip build at standard quality: ~50 credits. At Final Quality: ~120 credits.

---

## Approval gate (every project)

The Owner approval required before any public release. The handoff doc (`07_handoff_to_runway.md` in each project's ACTIVE_PROJECTS folder) c