# Bid Rendering Rules - hard lessons from the 59-73 batch (2026-06-15)

These exist because a first pass hand-rolled the client and GP PDFs with raw
reportlab and shipped slop: overlapping header text, fields running off the
page edge, and truncated 8-figure dollar amounts. Do not repeat it.

## 1. Render the client proposal with the production generator
Use `bridge/documents.py:generate_proposal(...)`. Never hand-roll reportlab
tables for a client proposal. Pass:
- `tonnage` = structural tons WITH connections folded in and the stage
  allowance already applied (it drives Section A fab + erection).
- `joist_tons`, `roof_deck_sf`, `composite_deck_sf`, `anchor_count` = the
  stage-adjusted quantities (Section B).
- `bid_number`, `project_meta` (address, owner, eor, architect,
  drawing_set_label), `scope_text`.
The generator produces the navy/gold header band, project-info grid, CSI
Division 05 table, itemized Section A/B pricing, capabilities, SOV, exclusions,
and signature. It also runs its own pdf_qc (R-01 requires visual inspection).

## 2. Stage allowance goes into QUANTITY, never a line item
Per `bridge/bid_rates.py` DRAWING_STAGE_ADDERS: "apply to QUANTITY, never as a
line item." Multiply tonnages / SF / counts by (1 + adder). Do not add a
"stage adder" pricing row to a client document.

## 3. Connections fold into structural tonnage
Connection material is fabricated and erected steel. Fold the connection
allowance tons into the structural tonnage so it prices at fab + erection. The
"$5,800 blended" connection figure is internal-GP reasoning only, never a
client line.

## 4. Engineering folded, deck in scope, no suppliers or precedents
Engineering and detailing are folded into fab and erection rates (never a
priced line). Deck supply and install is always in scope. No supplier names and
no precedent projects on client documents.

## 5. Validate AND visually inspect before delivery
Run `.claude/skills/governance/scripts/validate_bid_output.py` on the client
markdown (non-zero blocks export). Then render the PDF to images
(pdftoppm) and actually look at every page. The generator's pdf_qc R-01 fails
until a human/agent has visually inspected. Do not deliver on a blind render.

## 6. Cowork mount write hazard - write to NEW paths
In-place overwrites of existing files in the Cowork project mount silently
revert (an immediate read sees the new bytes, a later read returns the old
file). Confirmed on this batch: client PDFs copied over existing files showed
4 pages right after write, then 1 page (the original) on re-read. Write final
deliverables to NEW paths (a fresh dated folder or new filenames), or use
`.claude/skills/governance/scripts/safe_write.py` (atomic os.replace with
verify/retry) for protected files. Always re-read page count and content AFTER
writing to confirm persistence.


## 7. Build a 3D model on EVERY estimate (added 2026-06-15)
Every bid estimate builds an estimate-grade 3D coordinate model, not only bids
with a Tekla model. From the footprint and bay grid: place columns at grid
intersections, add perimeter and roof beams, write
`<bid>/model/<bid>_coordinate_members.json` and an STL via
`bridge/fabrication.py:generate_stl(members)`, and render a frame viewport to
`<bid>/renders/<bid>_MODEL.png`. The model aids the estimate (member count,
massing) and anchors the render. Visualization and QC only - it never changes
validated tonnage, AISC weights, or rates. Low-confidence placements are flagged
and never feed a price.

## 8. The page-1 render is required - working tooling
Generate a photoreal structural-steel-frame illustrative render and pass it as
`render_path` to generate_proposal. Working as of 2026-06-15:
- OpenAI `gpt-image-1` (images.generate, 1536x1024) is the current default. It
  produced clean photoreal steel frames. Prompt for the structural steel frame
  (columns, beams, open-web bar joists, roof deck), white background, no people,
  no text, no logos.
- Preferred when available: image-condition on the `_MODEL` frame viewport so the
  render matches real massing - Gemini `gemini-2.5-flash-image` (Nano Banana,
  generateContent with the frame as a Part) or OpenAI `images.edit`. On
  2026-06-15 Gemini image models returned 429 quota-exhausted, so gpt-image-1
  generate was used.
- API keys load from the virtualoffice `API Keys/` folder (Gemini API.txt,
  OpenAI API.txt). Never read or surface that folder in output; load the value
  into a variable via the project loaders and use it.
- Label AI renders illustrative. Client proposal only, never the -GP. A client
  proposal without a page-1 image is a defect.


## 9. Two images, fixed placement (added 2026-06-15)
Client proposals carry TWO illustrative images:
- PAGE 1 cover: AI render of the COMPLETED, finished building exterior. Generate
  with gpt-image-1 (prompt: finished building exterior, daytime, no people, no
  text, no logos/signage). Save `<bid>/renders/<bid>_BUILDING.png`. Pass as
  generate_proposal `render_path`.
- BEFORE EXCLUSIONS: the photoreal structural-steel-FRAME render
  `<bid>/renders/<bid>_render.png`. Pass as the `frame_image_path` kwarg
  (added to bridge/documents.py:generate_proposal 2026-06-15; renders the image
  under a "STRUCTURAL STEEL FRAME (3D MODEL)" heading just before EXCLUSIONS).
Keep the `_MODEL.png` frame viewport and the STL as engineering 3D-model
artifacts. Both proposal images are illustrative and never on the -GP report.