---
name: Steel and Building Render Pipeline
description: >
  Repeatable Cowork pipeline for producing photoreal structural steel and
  finished-building renderings for Your Company. Three input paths anchored
  to real geometry or real photos so output beats text-only AI image tools.
  Stands alongside VIDEO_STUDIO.md and ANTI_AI.md. DO NOT use Runway.
  Tooling is the Your Company stack: Google Ultra (Gemini / Imagen / Nano Banana)
  for stills and image-conditioned renders, OpenAI (gpt-image) as alternate,
  Google Veo for motion (turntables, fly-arounds). Claude stages everything
  ready-to-run; Joseph executes; Owner approves before anything public.
version: "1.1"
updated: "2026-06"
depends_on:
  - ANTI_AI.md
  - VIDEO_STUDIO.md
---

> Tooling note (2026-06-08, Owner): Runway is OUT for steel renders. Use the
> Google Ultra plan (Gemini / Imagen / Nano Banana) first, OpenAI gpt-image as
> alternate, Veo for motion. The text-only concept path produces structurally
> wrong frames (bad rafter pitch, missing purlins, misaligned columns) and is
> not acceptable. Anchor to real geometry or a real photo. Do not present a
> text-only render as a real building.

# Steel and Building Render Pipeline

This is the Phase 1 capability from the website + rendering roadmap. It makes
the Video Studio able to produce photoreal steel and building renderings on a
single Cowork prompt. The renders feed the yourcompany.example.com project gallery
and proposal cover pages.

## Why this beats text-only AI image tools

Generic AI image tools hallucinate steel from a text prompt with no geometry
behind them. Members float, connections are fake, proportions drift. Your Company
runs in-house Tekla detailing on every job, so renders can be anchored to real
model geometry and real site photos. That anchor is the entire advantage.
Always prefer the highest-fidelity input path available for the job.

## The three input paths (best to worst fidelity)

### Path 1 - Tekla-anchored render (highest fidelity)
Use when a Tekla model exists for the job.
- Export model geometry to a neutral format (IFC, FBX, OBJ, or a clean
  isometric/elevation screenshot from Tekla).
- The export becomes the structure reference. The render tool dresses it with
  materials, light, and environment but does not invent the frame.
- Real members, real connections, real bay spacing. This is the path that
  produces a render a structural engineer will not flinch at.
- Tooling: Gemini / Nano Banana image edit conditioned on the geometry export
  (Google Ultra), OpenAI gpt-image as alternate. Never text-only for this path.

### Path 2 - Reference-photo conditioned (high fidelity)
Use when there is a real photo of the building (built or shelled) or a close
visual reference of the look Owner wants.
- Feed the real photo as structure and style reference so output matches Nano
  Cube's actual work, not stock steel.
- Reference library lives in Website Rebuild/assets/reference/ and
  Video Creation/ASSETS/reference/ (Modera Art Park exoskeleton, dark
  steel-and-glass shells, plus any real project photos).
- Tooling: Gemini / Nano Banana image edit with the photo as reference
  (Google Ultra), OpenAI gpt-image as alternate.

### Path 3 - Concept render from drawings or sketch (directional)
Use when there is no model and no photo yet, only a layout, elevation, or
sketch.
- Generate a directionally accurate concept. Label it CONCEPT in the filename
  and on any internal share. Never present a Path 3 image as a real project.
- Tooling: Gemini / Nano Banana (Google Ultra), OpenAI gpt-image as alternate,
  drawing/sketch as reference where one exists.
- Warning: pure text-to-image hallucinates structure. The 2026-06-08 concept
  test produced wrong rafter pitch, missing purlins, and misaligned columns.
  Use this path only for loose mood, never as a real building.

## Motion (when a still needs to move)

For turntables, slow fly-arounds, and assembly-sequence shots:
- Take an approved still (from any path) as the first frame.
- Google Veo image-to-video (Google Ultra), 5-8s per clip. OpenAI Sora as
  alternate. No Runway.
- One motivated move per clip (slow orbit, push-in, crane-up). No random drift.
- Stitch multiple 5s clips for a full turntable. Never generate one long clip.

## Render style token - Style 01 Industrial Cinematic

Renders are photoreal and color-accurate. The Molten/Carbon brand palette is
for the website UI and graphic overlays, NOT a tint on the steel. Steel reads
as real steel. Warmth comes from golden-hour light, not an orange filter.

```
STYLE TOKEN - YOUR COMPANY STEEL RENDER (STYLE 01 INDUSTRIAL CINEMATIC):
Subject: conventional rolled structural steel, accurate members and connections
Light: low golden-hour sun, single direction, long soft shadows
   (or: overcast soft daylight for a neutral product look)
Environment: real Texas job-site or finished-site context, grounded scale
Camera: shot on Sony FX3, 24mm or 35mm, f5.6, architectural perspective,
   verticals kept true (no keystoning)
Grade: natural color, controlled highlights, deep but detailed shadows
Detail: mill-scale and primer texture on steel, real bolt heads, weld seams,
   deck profile visible, fine photographic grain
```

Append the style token verbatim to every render prompt in a set so a multi-
image set stays visually consistent (same discipline as ANTI_AI.md Law 3).

## Anti-AI laws that apply to stills

From ANTI_AI.md, the ones that matter most for architectural renders:
- Law 2: one light source, one direction. Name it every time.
- Law 3: lock the style token across the whole set.
- Law 9: physics. Steel sits on real foundations, casts real shadows.
- Law 13: NO readable text in frame. No signage, no banners, no labels on the
  building. Composite any wordmark or address in post.
- Law 14: NO distant or silhouetted human figures. Either crop people out
  entirely (preferred for shells) or place one clearly-rendered worker in
  medium shot for scale. No half-human shapes at distance.
- Law 15: logos, project names, and stat callouts are composited in post, not
  generated.
- Law 16: spell out or post-composite all symbols.
Add for renders specifically:
- Keep verticals true. Skewed columns read as fake instantly.
- Do not invent member sizes or connection types on a Path 1 job. The geometry
  reference is the authority, exactly as AISC weights come from the validator,
  not from the model.

## Output specs

| Use | Aspect | Size | Notes |
|---|---|---|---|
| Website gallery card | 16:10 | 2048px wide min | Matches the work-grid on the site |
| Website hero / full-bleed | 16:9 | 3840px wide | 4K for retina |
| Proposal cover render | 4:3 or letter-ratio | 300 DPI at print size | Cover use only, never inside the -GP report |
| Turntable / fly-around | 16:9 | 1080p, 4K upscale optional | 5-6s clips stitched |

Renders land in Website Rebuild/renders/ for the site and, for a specific job,
in Video Creation/OUTPUTS/<ProjectName>/.

## The gated workflow (five phases, hard human gate)

```
1. CAPTURE   Collect inputs: Tekla export OR reference photo OR drawing.
             Pick the highest-fidelity path available.
2. PLAN      Choose path, shot list (angles), and output specs. Write the
             style token for the set.
3. STAGE     Write ready-to-run prompt blocks, one per image, plus a run
             sheet. Save to ACTIVE_PROJECTS/<Name>/.
4. APPROVE   Joseph reviews the staged plan. Nothing generates without his
             go. (Gate.)
5. EXECUTE   Run in Gemini / Nano Banana on the Google Ultra plan (Claude in
             Chrome drives gemini.google.com / aistudio, or Joseph runs it),
             OpenAI gpt-image as alternate. Generate 2 takes per hero image.
             Composite any text/logo in post. Owner approves before public.
```

## QA checklist (before marking a render done)

```
[ ] Highest available input path was used (Tekla > photo > concept)
[ ] Path 1: members and connections match the geometry export, nothing invented
[ ] One light source, one direction, consistent across the set
[ ] Style token appended verbatim to every prompt in the set
[ ] Verticals true, no keystoning
[ ] No readable text, signage, or labels in frame (Law 13)
[ ] No distant or silhouetted figures (Law 14)
[ ] Logos / project names / stats reserved for post composite (Law 15)
[ ] Steel reads as real steel, not orange-tinted by brand color
[ ] Concept images labeled CONCEPT in filename and on share
[ ] Output sized per the spec table for its destination
```

## The Phase 1 acceptance gate

The roadmap's bar: a first test set (one Tekla-anchored render, one
reference-conditioned still, one image-to-video turntable) placed side by side
with the four Google-AI I-beam images Owner sent. The Your Company set must be
visibly more accurate and more real. Joseph approves before this becomes a
standing capability. Test set is staged in
ACTIVE_PROJECTS/Steel_Render_Test_Set/.

## Proven workflow (2026-06-08) - drawing-anchored, executed via Cowork

This is the exact procedure that produced the accepted 10K Shell renders.
Use it as the standing recipe.

1. PICK A DRAWING. Any structural sheet for the job. Best anchors:
   - Cover-sheet BUILDING ELEVATION -> finished-building render (facade match).
   - ROOF FRAMING PLAN / structural sections -> steel-erection render (system match).
2. EXTRACT A CLEAN ANCHOR. Rasterize the PDF page (PyMuPDF at ~2.2x), crop to
   just the elevation or framing drawing (drop title block and schedules).
   Save to the job's renders/ working area and to assets/tekla/.
3. CONDITION IN GEMINI (Google Ultra, gemini.google.com), driven by Cowork:
   - PowerShell puts the anchor PNG on the clipboard
     ([System.Windows.Forms.Clipboard]::SetImage) and force-foregrounds Chrome
     (Win32 SetForegroundWindow on the Chrome PID).
   - Chrome MCP clicks the composer; Windows MCP sends a real ctrl+v (the
     synthetic paste does not carry the clipboard image, the OS keystroke does).
   - Type a precise prompt: name the exact structural system, "match the
     attached drawing", true verticals, one light direction, no text, no
     people, no orange tint on steel, 16:9. Send.
   - Poll until the image renders. Download (hover -> download icon).
   - Windows MCP moves the file from Downloads into the job's renders/.
4. VARIANTS + FUSION. Generate 2-3 variants (angle/light, finished vs erection).
   To fuse: paste the best finished variants back into one Gemini chat and ask
   for a single polished hero. Save as <job>_MASTER_*.jpg.
5. VERIFY against the drawing and the QA checklist above. Concept/text-only
   output is unreliable on geometry - always anchor.

Engines: Gemini / Nano Banana on Google Ultra is the working engine. OpenAI
gpt-image needs a ChatGPT login (do not log in or use raw keys). Antigravity
is a coding IDE, not an image generator. No Runway.

## Bid proposal integration (wired 2026-06-08)

The client proposal PDF auto-embeds a drawing-anchored render as a cover image.

- Save the chosen render into the bid's renders/ subfolder. Prefer a filename
  containing MASTER (the locator picks MASTER first, else the newest image).
- bridge/bid_documents.py:find_render(project_name, bid_number) locates it.
- bridge/agents/bid_chain.py step 9 passes it to
  bridge/documents.py:generate_proposal(..., render_path=...), which inserts
  the image after the project-info table with the caption:
  "Illustrative rendering generated from this project's structural drawings.
  Not a photograph of a completed building."
- CLIENT PROPOSAL ONLY. Never on the -GP report. No supplier names (renders
  never show them). Always labeled illustrative. Run validate_bid_output.py
  before export. Re-run `self test` in Chat after any bridge change.

## ACCURACY LIMIT - read before any render goes to a client (2026-06-09)

AI image generation INTERPRETS a drawing. It does NOT reproduce the frame.
Even conditioned on a framing plan or a 3D structural isometric, the model
swaps member systems, changes bay counts, and invents framing. Field test
2026-06-09: a Chastang Ford render anchored on the Tekla iso came back with
the heavy joist girders replaced by a lighter joist system and light-gauge
wall framing that is not on the drawing. Owner (fabricator) rejected it on
sight. It was quarantined to renders/_rejected/.

Rules that follow from this:
- AI renders are for FINISHED-building and ATMOSPHERIC ILLUSTRATIVE visuals
  only - anchored on an architectural ELEVATION or a reference photo. A
  finished facade reads as correct; a bare frame exposes every wrong member.
- Do NOT put an AI structural-FRAME render (erection stage, exposed steel)
  into a bid proposal or onto the public site, and never claim member or
  framing accuracy for an AI image.
- A member-accurate frame image comes from TEKLA - render the model in Tekla
  or export its viewport. That is the only source of a structurally correct
  steel image. AI cannot do it.
- Label every AI render "illustrative, not a photograph of a completed
  project." Steel-frame renders need a Tekla source, not Gemini.

This supersedes any earlier "steel-erection render anchored on the framing
plan" guidance in this file for client-facing use. Such renders are concept
mood only, internal, never shipped.

## Page-1 proposal image - REQUIRED on every bid (2026-06-09)

Every bid proposal carries a project image on page 1. Resolution order:
1. TEKLA VIEWPORT EXPORT - member-accurate frame geometry, and the ALWAYS
   source for any structural-frame image. Performed on every bid that has a
   detailing model: Joseph sets a rendered isometric 3D view in Tekla
   Structures, File > Export to image (1920px+), and saves it to the bid's
   renders/ folder as <bid>_TEKLA.png. AI never fills this slot.
2. If no Tekla model exists yet (early bid), a FINISHED-building or atmospheric
   ILLUSTRATIVE render (Gemini, anchored on an architectural elevation or
   reference photo), labeled illustrative. Never an AI structural-frame image.

Wiring (all in the bridge, runs in the Chat-tab pipeline):
- bridge/tekla_viewport.py - find_tekla_viewport() / require_tekla_viewport().
- bid_chain step 8b_tekla_viewport runs every bid; records {ok, path} or the
  export-required action (ok=False is a gate, not a failure).
- bid_documents.find_render prefers tekla/viewport, then a fused MASTER, then
  newest image in the bid renders/ folder.
- documents.generate_proposal embeds the image on page 1; caption reads
  "Tekla structural model viewport. Member-accurate frame geometry ..." when
  the filename contains tekla/viewport, else the illustrative caption.
- If no image is staged, the proposal still generates (text-only) and the bid
  is flagged to add the page-1 image before sending. Run `self test` in Chat
  after any bridge change.
