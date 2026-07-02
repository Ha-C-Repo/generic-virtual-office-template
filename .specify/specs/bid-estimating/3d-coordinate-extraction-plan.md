# Plan: Generate 3D Coordinates from Drawings During Bid Estimating

**Status:** Proposal for review (Owner + Ivan). Not yet built.
**Author:** Cowork, 2026-06-09
**Why now:** The page-1 proposal image and gallery require member-accurate
frames, which today only Tekla can produce because the takeoff has no geometry.
If the bid process assigned 3D coordinates to each member, Your Company could build
its own member-accurate model in-house: render the page-1 viewport without a
Tekla round-trip, and get a visual QC cross-check on every bid.

## 1. What we have today

- `bridge/lift_clone/takeoff.py` extracts marks + AISC shapes from sheet TEXT
  (regex), infers member type from the mark prefix, and tags confidence. It has
  NO spatial information - no grid, no levels, no endpoints.
- `bridge/fabrication.py:generate_stl(members)` already builds an STL, but it
  needs `x_ft, y_ft, z_ft` per member and only extrudes along one axis from an
  origin. With no coordinates it stacks everything at 0,0,0.
- `bridge/stl_thumbnail.py:render_stl_thumbnail()` renders an STL to an
  isometric PNG (trimesh + matplotlib, already deps).
- `bridge/aisc_validator.py` is the authority for shape weights (2,299 shapes).
- `bridge/exporters/tekla_xml_gen.py` already maps the takeoff to Tekla PowerFab
  XML (data OUT to Tekla). The orchestrator notes IfcOpenShell + PyNite as the
  intended open-source replacement for PowerFab - neither is installed yet.

## 2. The real problem, decomposed

A 3D model needs two things the drawings hold separately:

- A COORDINATE FRAME: the column grid (letters A,B,C... and numbers 1,2,3...)
  with bay dimensions gives X/Y. Level datums on elevations/sections (T.O.
  Slab, T.O. Steel, roof) give Z.
- MEMBER PLACEMENT: each member's endpoints expressed against that frame.
  Columns sit at a grid intersection and run base elevation -> top. Beams,
  girders, and joists span between two grid lines at a given level.

So the work is: (a) build the grid + datum frame, (b) place each detected member
onto it, (c) emit coordinate-tagged endpoints.

## 3. Approach - phased

### Phase 1 - Grid and datum extraction (the coordinate frame)
- Vector-first: use PyMuPDF `page.get_drawings()` to pull line work from the
  foundation/roof-framing plan. Detect grid bubbles (circles with a letter or
  number) and the dimension strings between them to compute X spacings (along
  numbered lines) and Y spacings (along lettered lines). Output a grid map:
  grid label -> coordinate (ft).
- Datums: parse level callouts from elevations/sections (T.O. Slab = 0'-0",
  T.O. Steel = +X, roof bearing = +Y). Output a level map: name -> elevation.
- Confidence tag the frame. If grid/dims can't be read (scanned/dirty set),
  fall back to the vision router (Phase 1b) or flag for human entry.

### Phase 1b - Vision fallback (scanned or non-vector sets)
- Route raster/scanned sheets to multimodal extraction (Gemini / GPT-4o):
  "return the grid labels, their X/Y spacings in feet, and the level
  elevations." Same output schema as Phase 1. Lower confidence; always flagged.

### Phase 2 - Member placement to grid
- Extend the framing-plan reader so each detected member carries its grid
  endpoints and level: column at (gridX, gridY), base->top; beam/girder/joist
  from gridA to gridB at level L. Vector path: snap plan line endpoints to the
  nearest grid intersections. Vision path: ask for "start grid, end grid,
  level" per member.
- Columns come from the column schedule + grid; beams/joists/girders from the
  framing plan lines and the joist designation callouts.

### Phase 3 - Coordinate assembly
- Produce a coordinate-tagged member list:
  `{mark, shape, type, start:[x,y,z], end:[x,y,z], level, confidence, source_sheet}`.
- This is the single new artifact. It is a superset of today's BOM, so the
  existing tonnage/AISC path is unchanged - coordinates are additive.

### Phase 4 - Model build and render (in-house)
- Extend `fabrication.generate_stl` to accept `start`/`end` endpoints (extrude
  the section between two 3D points) instead of origin+length+axis only.
- Build the STL from the coordinate-tagged list -> `render_stl_thumbnail()` ->
  isometric PNG. Save to `<bid>/renders/<bid>_MODEL.png`.
- OPTIONAL (dependency gate): build a real IFC via IfcOpenShell from the same
  list. IFC is the durable, exportable, viewer-friendly model and the path the
  orchestrator already named for replacing Tekla PowerFab. Requires adding
  IfcOpenShell (+ PyNite if we later want analysis) - must clear the
  Dependency-tax gate in `.specify/governance-delta.md` first.

### Phase 5 - Integration and verification
- Feed the in-house model viewport into the page-1 image system as the
  AUTOMATED fallback when no true Tekla export exists yet, labeled
  "in-house model viewport from verified takeoff" - visibly distinct from a
  Tekla Structures export. `bid_documents.find_render` already prefers
  tekla/viewport; add `model` as the next tier so a true Tekla export still
  wins.
- Confidence and the Ivan gate: per the constitution's verify-don't-generate
  rule, every coordinate carries high/medium/low. Low-confidence members are
  flagged for human check and shown in a different color in the render. The
  model is a VISUAL and QC aid, never the system of record.
- QC cross-check: sum member lengths x AISC weight from the coordinate model
  and compare to the validated takeoff tonnage. A divergence beyond a threshold
  flags a missed or mis-placed member - a free sanity gate on every bid.

## 4. What this is NOT

- It does NOT replace Tekla detailing. Tekla remains the fabrication system of
  record and the source of the truly member-accurate proposal image when a
  detailing model exists. The in-house model is estimate-grade geometry for
  visualization, QC, and an early page-1 image before detailing.
- It does NOT touch the AISC-validated tonnage or the CEO-locked rates.
  Coordinates are additive metadata.

## 4b. Render tiers - matplotlib (fallback) and Blender (quality, gated)

The coordinate model is the single source of truth. Renderers sit on top of it
and are swappable. Two tiers:

- TIER 1 - matplotlib/trimesh thumbnail (have today, in the EXE). Instant, gray,
  QC-grade. Always available, zero new dependency. The default fallback.
- TIER 2 - Blender (quality). Member-accurate by construction (it renders exactly
  the coordinates given - no AI interpretation), free, and headless-scriptable.
  This is the proposal-cover and gallery-grade tier matplotlib cannot reach.

Blender architecture - treat it like Tekla, an EXTERNAL tool, NOT a bundled dep:
- Installed once on the machine (Joseph/Owner), invoked by the bridge via
  `subprocess`: `blender --background --python build_frame.py -- <coords.json> <out.png>`.
- DO NOT pip-install `bpy` into the PyInstaller-frozen EXE. It adds hundreds of
  MB and version-pinning pain and would breach the no-new-infra-in-the-EXE line.
  The bridge shells out to an installed Blender; if Blender is absent it falls
  back to Tier 1 automatically.
- Eevee for fast turnaround, Cycles for hero stills. Apply the Your Company
  Style 01 material/light setup (mill-scale steel, golden-hour key light).
- Output: still PNG to `<bid>/renders/<bid>_MODEL.png`, and optionally a short
  turntable for the gallery.

Preferred build path (open BIM stack): coordinate list -> IFC via IfcOpenShell
-> import to Blender with the Bonsai (BlenderBIM) add-on, which reads IFC
natively -> render. IFC + Bonsai + Blender is also the real open-source
replacement for Tekla PowerFab the orchestrator already named. A simpler
non-IFC path also works: a Blender Python script reads the coordinate JSON
directly and instantiates each member as an extruded AISC profile.

Gate: Blender (and IfcOpenShell/Bonsai) is an external-tool + dependency
decision. Clear the Dependency-tax / Monolith-first gates in
`.specify/governance-delta.md` before adopting. The matplotlib tier ships first
and needs no gate.

Caution: Blender renders what the coordinates say. An incomplete takeoff yields
a clean render of wrong steel. The confidence tags (Section 5) and the tonnage
QC cross-check still decide whether a render may leave the building. Blender
raises quality, it does not raise accuracy - accuracy comes from the coordinates.

## 5. Tooling and dependencies

- Have now: PyMuPDF (get_drawings), numpy, trimesh, matplotlib, the AISC
  validator, Gemini/GPT-4o for the vision fallback.
- New only if we go to quality renders: Blender (external app, subprocess,
  not bundled) and, for the open-BIM path, IfcOpenShell + the Bonsai add-on
  (+ optional PyNite for analysis). All gated - do not add without sign-off.
  The matplotlib STL + thumbnail tier needs NO new dependency and ships first.
- New module suggestion: `bridge/lift_clone/geometry.py` (grid + datum + member
  placement), and an endpoint mode in `fabrication.generate_stl`.

## 6. Risks and limits

- Scanned/low-quality sets: vector extraction fails; vision fallback is lower
  confidence. Always flag, never silently guess (constitution).
- Sloped roofs, cambered members, complex framing, multi-level: Z handling gets
  harder; start with single-story flat/low-slope shells (the bulk of the work).
- Coordinates are estimate-grade. Good enough for a viewport and a QC check,
  not for fabrication. Keep the Tekla-is-truth line bright.

## 7. Suggested first slice (prove it on one bid)

1. One clean VECTOR framing plan (e.g., a recent shell bid).
2. Phase 1 grid + datum extraction only -> grid map + level map, shown for
   human confirm.
3. Columns only: place columns at grid intersections, base->T.O. Steel.
4. STL + thumbnail of just the column grid. Eyeball against the plan.
5. If the column grid lands true, add beams/girders, then joists.
Ship the thin slice, get Ivan's read, then widen. No big-bang build.

## 8. Decisions needed from Owner / Ivan

- Go/no-go on building the in-house coordinate model at all (vs. keeping Tekla
  as the only model source).
- IFC (IfcOpenShell) vs. STL-only for the first build (dependency gate).
- Adopt Blender as the Tier-2 quality renderer (external tool) - and if so,
  direct coordinate->Blender script vs. coordinate->IFC->Bonsai->Blender.
- Accuracy bar for an in-house viewport to be allowed on a proposal page 1, or
  whether in-house model viewports stay internal/QC-only and only true Tekla
  exports ever reach a client.
