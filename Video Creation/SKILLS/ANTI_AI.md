---
name: Anti-AI Video Discipline Guide
description: >
  Mandatory rules, techniques, and prompt patterns that eliminate every
  known AI video artifact and make generated footage look like real camera
  work. Applies to ALL Runway prompts written by Claude. Contains the 12
  core anti-AI laws, the forbidden prompt patterns, the physics grounding
  system, the film medium system, and the consistency lock protocol. Load
  this whenever writing Runway prompts for any production context.
version: "1.0"
updated: "2026-05"
---

# Anti-AI Video Discipline Guide

The difference between video that looks AI-generated and video that looks
like real footage is NOT resolution or model quality. It is internal
consistency across four layers: visual style, lighting, character identity,
and camera behavior. When all four drift, even one clip breaks the
illusion. When all four are locked, even a stylized AI video feels real.

---

## THE 16 LAWS — NON-NEGOTIABLE FOR EVERY PROMPT

### Law 1 — Always Image-to-Video for Any Clip With a Person
Text-to-video asks the model to invent character appearance every frame.
Image-to-video anchors the appearance from the first frame forward.
Use I2V for 100% of clips containing human subjects. No exceptions.

**Correct Workflow:**
1. Generate a reference image in Gen-4 Image or Gen-4 Image Turbo
2. Lock that image as the character anchor
3. Use it as the first frame input for EVERY clip featuring that character
4. For scene transitions, extract the Last Frame and use as First Frame of next clip

### Law 2 — One Light Source, One Direction, Per Scene
Conflicting light directions are the most common artifact that breaks
realism. The human eye detects this instantly.

**Correct:** "warm afternoon sunlight entering from the left through
floor-to-ceiling windows, casting long directional shadows across the
conference table surface"

**Wrong:** "cinematic lighting" (undefined — model invents a new lighting
setup on every frame)

Always specify:
- Direction (left, right, above, behind, front)
- Character (warm/cool/neutral)
- Source name (sunlight, tungsten practical, fluorescent overhead, candlelight)
- Shadow behavior (soft diffused / hard directional)

### Law 3 — One Visual Style, Locked Across All Clips
Mixing photorealistic clip 1 with painterly clip 2 is an immediate AI tell.
Pick one style system from VIDEO_STUDIO.md Section 10 and apply it to every
prompt in the production, word for word.

**Consistency lock:** Copy-paste the style qualifiers into every prompt.
Do not paraphrase them. Exact wording = consistent style execution.

```
STYLE LOCK TOKEN (copy into every prompt):
"shot on [CAMERA BODY], [LENS], photorealistic, [LIGHTING DESCRIPTOR],
[GRADE DESCRIPTOR], fine film grain"
```

### Law 4 — Camera Has Weight, Inertia, and Intention
Random floating camera = AI tell. Every camera movement must have:
- A starting position
- An ending position
- Motivation (why is it moving?)
- Physical behavior (speed, smoothness, weight)

**Wrong:** "camera movement"
**Wrong:** "cinematic camera"
**Correct:** "camera performs a slow, smooth push-in from medium shot to
medium-close-up over the full 5-second duration, as if mounted on a
fluid-head tripod dolly, decelerating gently at the end"

### Law 5 — Keep Clips Short (5-6 Seconds Maximum)
AI video consistency degrades proportionally with duration. At 10 seconds,
character features drift. At 15 seconds, the scene morphs.
5-second clips are the sweet spot for maximum consistency per frame.
Use Stitch to assemble longer content — do not generate long clips.

### Law 6 — Fill the Frame With the Subject
Wide shots with many small figures are where AI video fails most
catastrophically: anatomical errors, morphing clothing, inconsistent
positions. Portrait photographer rule: fill the frame, simplify the
background, let the subject dominate.

**Wrong for AI:** Wide establishing shot with 12 office workers at their desks
**Correct for AI:** Medium shot of ONE person at a clean desk, background
soft and out of focus

If you MUST have a wide shot, make it environment-only with no people.

### Law 7 — Specify a Film Medium, Not a Genre
"Cinematic" means nothing to a model. "Shot on ARRI Alexa Mini LF with
a 32mm Cooke S4 lens at T2.8" gives the model a concrete visual target.

**Medium Specifications by Style:**

| Aesthetic | Camera Body | Lens | Format |
|---|---|---|---|
| Corporate cinematic | ARRI Alexa Mini LF | 32mm Cooke S4 | 4.5K ProRes |
| Luxury editorial | Hasselblad X2D or Phase One | 80mm | Medium format |
| Documentary authentic | Sony FX3 | 35mm equivalent | S-Log3 |
| Bold commercial | RED Komodo-X | 24mm Sigma Art | REDCODE |
| Premium product | Phase One IQ4 or Canon EOS R5 | 100mm macro | Studio strobe |
| Social/UGC feel | iPhone 15 Pro or Samsung S24 | Standard | 4K 60fps |

### Law 8 — Add Film Grain
Film grain is the single fastest fix for the synthetic sheen of AI video.
It adds texture that makes generated footage feel photographically real.
Always append to every prompt: **"fine film grain, 35mm grain structure"**
or for premium looks: **"subtle ARRI Alexa sensor noise"**

### Law 9 — Describe Physics, Not Just Motion
AI video breaks physics constantly: floating objects, fabric that doesn't
settle, hair that doesn't move with gravity, liquids without viscosity.
Ground every clip in physical reality by describing physical laws explicitly.

**Wrong:** "steam rising from coffee cup"
**Correct:** "steam rises slowly and disperses from the dark surface of the
coffee, curling upward in soft wisps before dissipating into the air"

**Wrong:** "woman walking"
**Correct:** "she walks with even, measured steps, her jacket hem swaying
slightly with each stride, heels making contact with the polished concrete"

### Law 10 — One Action Per Clip
Asking for multiple scene transitions or multiple character actions in one
prompt causes visual drift — the model reinvents the scene mid-generation.

**Wrong:** "The man walks to the window, looks out over the city, then
turns back and shakes hands with a colleague"

**Correct Clip 01:** "The man walks steadily toward the floor-to-ceiling
window, his reflection appearing in the glass as he approaches"
**Correct Clip 02:** "He stands at the window, looking out across the
Houston skyline, subtle breath visible in his chest, camera holds static"

### Law 11 — Never Describe Hands in Close Proximity to the Frame
Hands are the most common failure point of AI video and images.
If hands appear in a close-up or ECU, the model will generate distorted,
extra-fingered, or morphing hands.

Rules:
- Never use ECU or CU framing for clips where hands are required
- If hands must be visible, use MS or wider and keep them in soft focus
- Describe hand positions neutrally: "resting on the table" not "gesturing"
- Safer: describe character looking or turning toward something

### Law 12 — Avoid AI Clichés in Scene Selection
AI video defaults to a recognizable set of visual clichés. These immediately
signal "AI generated" to a trained viewer.

**Banned Clichés:**
- Aerial establishing shot of a generic city skyline
- Generic "business handshake" between two people
- Person typing on laptop looking inspired
- Lens flare on every shot
- Slow-motion confetti or celebration
- Abstract flowing liquid or particles as filler
- "Spinning logo" reveal without context
- Generic man in suit walking toward camera on a white background

**Replace With:**
- Specific location details (named building, named street, real landmark)
- Purposeful action with context (reviewing documents, pointing at data)
- Environment texture instead of character (the office as it actually looks)
- Motivated, specific camera moves

### Law 13 — No Readable Text or Documents in Frame
Generative video models cannot render coherent English (or any language)
text. They produce *plausible-looking gibberish* — letterforms that look
correct from a distance but read as garbage on inspection. This is the
single most reliable AI tell to a trained viewer.

**What this breaks:** balance sheets, contracts, books, magazines, signage,
shop signs, computer screens, name tags, business cards, framed diplomas
on walls, license plates, packaging labels, whiteboards with writing,
notebooks with visible writing, anything with letters meant to be read.

**Failure case from production record:** a prior 30s build (2026-05-19), Beat 1.
A "FINANCE SHEET" rendered with column labels reading "ROITDA," "OZAANIOR
EFBAFITS," "DEBRECIRATORS," "MERN2INE," "BRITDA," "ORANNMNTIL ACTIVITES"
— the numbers below them looked fine, but every label was gibberish.

**The rule:** If text is essential to the shot, you have three options
and ONLY these three:
1. **Crop the text out of frame entirely.** Show the pen tip and the
   paper texture but never the readable area.
2. **Defocus the text into illegibility.** Shoot at a shallow depth of
   field with focus on a non-text element; text becomes abstract pattern.
3. **Composite real text in post.** Leave a clean plate during generation
   and overlay the actual content in After Effects/Premiere/DaVinci.

**Prompt language to enforce this:**
- "document held at an oblique angle; text appears as illegible texture only"
- "out-of-focus newspaper, text reads as soft gray pattern, no legible characters"
- "balance sheet shown only as numeric columns with shallow depth of field;
   any text characters render as out-of-focus impressionistic pattern"

**Never write in a prompt:**
- "the document reads FINANCE SHEET" → AI will try and fail
- "the screen shows quarterly revenue" → AI will invent garbled text
- "a sign that says OPEN" → AI cannot render signs reliably

### Law 14 — No Human Figures at a Distance, No Silhouettes
The uncanny valley is sharpest at two viewing distances: extremely close
(hand/finger-level detail) and far enough that a human reads as a small
figure. Silhouettes are worst of all — the brain expects a recognizable
human outline and AI produces "almost-human" shapes (missing heads,
fused limbs, torsos with wrong proportions).

**Failure case from production record:** a prior 30s build (2026-05-19), Beat 3.
A welder silhouetted at frame-right was generated with an indistinct
head/torso boundary — the figure read as headless from a distance, which
broke an otherwise strong industrial shot.

**The rule:** Every human in frame must be either (a) close enough to read
as a specific identifiable person (medium close-up or tighter, per Law 6)
or (b) cropped out of frame entirely. **No middle distances. No silhouettes.**

**Replace silhouetted figures with:**
- Their hands only (still subject to Law 11 if close to frame — use forearm)
- Their tools or equipment in foreground, character implied not shown
- A close-up on what they're working on (the weld bead, the I-beam joint,
   the document) with no figure in frame at all
- A different actor framed medium close-up

**Prompt language to enforce this:**
- "arc-welder I-beam, sparks falling, no human figure in frame"
- "the steel surface fills the frame; any worker present is cropped above
   shoulder line at frame edge"

### Law 15 — All On-Screen Data, Stats, Lower-Thirds, and Brand Marks Are Composited in Post
This includes:
- Stat cards / number callouts ("3¢ PER DOLLAR")
- Lower-third name supers ("THE OWNER / Founder")
- Wordmarks and logos (any company name)
- URLs and phone numbers
- Pricing, percentages, dates, statistics
- Captions / subtitles
- Bug graphics, watermarks, identifiers

**Failure cases from production record:**
- A prior 30s build, Beat 4: Stat card rendered as "3⁶ PER DOLLAR" with a
  malformed superscript instead of "3¢ vs 8¢" comparison.
- A prior 30s build, Beat 6: Wordmark rendered with garbled, misspelled letterforms
  (truncated, missing "ory").

**The rule:** During generation, leave a **clean plate** in the region
where text/data will live — usually an atmospheric backdrop with the
lighting and color palette of the rest of the spot. Composite the real
text/logo/stat in post using vector or canonical raster brand assets.

**Workflow steps when a clip needs on-screen data:**
1. Write the prompt with "no readable text in frame, no logos, no
   wordmarks, no numbers, no UI elements — clean atmospheric plate"
2. Generate the clip
3. In post, overlay the data using:
   - Canonical brand wordmark file from ASSETS/brand/
   - Real numbers/stats in brand-approved typography
   - Animated reveals matching the spot's pacing
4. Render the final master only after the composite is in place

**Prompt language to enforce this:**
- "no on-screen text, no graphics overlay, no UI; clean atmospheric plate
   for post-production data composite"
- "leave a clean negative-space region in the lower-third for a name super
   to be added in post"

### Law 16 — Spell Out Symbols and Special Characters; Never Ask AI to Render Them
Cent signs (¢), percent (%), degrees (°), ®, ™, ©, fractions (½), and
currency symbols ($, £, €) render unreliably. AI substitutes generic
glyphs ("⁶" for "¢"), superscript characters in random positions, or
omits the symbol entirely.

**In VO scripts**, write the words out:
- "three cents on the dollar" not "3¢ on $1"
- "fifty percent" not "50%"
- "ninety-eight degrees" not "98°"

**In on-screen data**, render the symbol in post (per Law 15) using
proper Unicode glyphs in the brand-approved typeface.

**Failure case from production record:** A prior 30s build, Beat 4 stat card
rendered with "3⁶" where "3¢" was intended.

---

## AI ARTIFACT IDENTIFICATION AND FIXES

### Artifact: Face/Character Drift Between Clips
**What it looks like:** Character's face changes subtly from one clip to
the next — different bone structure, slightly different features, clothes
that don't match.

**Fix:**
- Lock a reference image and use it as first frame on ALL character clips
- Use Fixed Seed in Runway settings — same seed across all character clips
- Keep visual style token identical in every prompt

### Artifact: Background Flicker or Morph
**What it looks like:** The background environment subtly changes or
flickers between frames — walls breathe, patterns shift, depth changes.

**Fix:**
- Use a reference image for the environment
- Keep environment descriptions identical between clips sharing a location
- Shorter clips (5s) maintain background stability better than longer ones
- Specify "static camera" for clips where background stability is priority

### Artifact: Temporal Inconsistency (Frame-to-Frame Drift)
**What it looks like:** Object positions jump slightly between frames,
clothing changes color, hair changes shape during the shot.

**Fix:**
- Shorter clips (3-5s)
- Simpler, less detailed backgrounds
- Single subject instead of multiple
- Specify "continuous, uninterrupted motion" in the prompt

### Artifact: Physics Violations
**What it looks like:** Liquid doesn't flow right, fabric is too stiff or
too elastic, objects appear to float, gravity seems variable.

**Fix:**
- Describe the physics explicitly (see Law 9)
- Keep physical interactions simple — one object doing one thing
- Use I2V to anchor the starting physical state of objects

### Artifact: Lighting Inconsistency Between Clips
**What it looks like:** One clip is warm-toned, the next is cool — as if
cut together from different times of day or different sets.

**Fix:**
- Lock a lighting descriptor string and copy it into EVERY prompt
- Never vary lighting direction even slightly between clips
- Build reference image with the correct lighting before production

### Artifact: Synthetic Skin / Plastic Face
**What it looks like:** Human skin looks waxy, overly smooth, HDR-enhanced,
or slightly translucent.

**Fix:**
- Append "realistic skin texture, natural skin imperfections, photographic
  skin tones, pores visible in close-up" to any clip featuring faces
- Use "shot on 32mm at T2.8" to specify moderate depth of field that
  softens without erasing texture
- Avoid ECU of faces unless using Act-One or Act-Two for performance

### Artifact: The "AI Glow" — Overly Beautiful Everything
**What it looks like:** Every surface gleams, every face is perfect, colors
are deeply saturated, shadows are perfectly placed. It looks like a screensaver.

**Fix:**
- Explicitly ask for imperfection: "slightly worn leather surface,"
  "natural dust particles visible in shafts of light," "scuffed concrete floor"
- Specify "muted color grade, desaturated shadows, low contrast" to dull the glow
- Documentary framing and handheld movement immediately counteract the AI glow

---

## THE FILM MEDIUM SYSTEM

Specifying a camera body, lens, and shooting format is the single most
powerful technique for escaping the generic AI aesthetic. These prompts
give the model a concrete visual target — a finite, real-world reference
that has thousands of examples in training data.

### High-End Cinematic (Feature Film / Premium Commercial)
```
"shot on ARRI Alexa Mini LF, 32mm Cooke S4 lens, T2.0,
anamorphic lens flare characteristic, horizontal squeeze,
ProRes 4K RAW, natural film grain"
```

### Corporate / Brand (B2B Video)
```
"shot on Sony FX6, 50mm Sony G Master lens, f2.8,
S-Log3 color profile, natural tungsten interior lighting,
full frame sensor, cinematic color grade"
```

### Luxury / Editorial (Fashion, Luxury Product)
```
"shot on Phase One IQ4 150MP, 80mm Schneider Kreuznach lens,
studio strobe main light, ISO 100, razor thin depth of field,
photorealistic medium format color rendition"
```

### Authentic / Documentary (Lifestyle, Wellness, Food)
```
"shot on Sony FX3 with 35mm equivalent lens, S-Log3,
available natural window light, handheld with slight organic
motion, raw indie film aesthetic, unprocessed natural color"
```

### Social / UGC (TikTok, Reels, Stories)
```
"shot on iPhone 15 Pro, 1x lens, 4K 60fps, natural colors,
slight overexposure from direct sunlight, authentic vlog aesthetic,
real-world ambient noise implied"
```

### High-Speed / Action (Sports, Launch Videos)
```
"shot on RED Komodo-X, 24mm Sigma Art lens, high frame rate
slow motion, high contrast color grade, ultra-sharp, commercial
athletic advertising aesthetic, no depth of field"
```

---

## CONSISTENCY LOCK PROTOCOL

For multi-clip productions, use this system to maintain visual consistency:

### Step 1 — Write the Style Token
```
STYLE TOKEN for [PROJECT NAME]:
Camera: [specific body and lens]
Lighting: [single source, direction, character]
Grade: [color grade descriptor]
Grain: [grain descriptor]
Format: [frame rate, resolution]
```
**Example:**
```
STYLE TOKEN — LUXURY / PREMIUM (STYLE 02):
Camera: ARRI Alexa Mini LF, 32mm Cooke S4, T2.0
Lighting: warm tungsten practical window light, left side, soft shadows
Grade: muted warm cinematic grade, deep shadows, controlled highlights
Grain: fine natural ARRI sensor grain
Format: 24fps, 4K
```

### Step 2 — Append to Every Prompt
The last sentence of every prompt must be the Style Token, word for word.
No paraphrasing. Identical wording = identical style execution.

### Step 3 — Generate Reference Image First
Before building the Workflow, generate one hero image in Gen-4 Image that
demonstrates the Style Token. This is the "color bible" for the production.
If the reference image doesn't match the intent, revise the Style Token
before generating any video.

### Step 4 — Lock the First Frame
Use the reference image (or a derivative of it) as the First Frame input
on every clip containing the main character or main environment.

---

## FORBIDDEN PROMPT PATTERNS

These prompt patterns are prohibited in all production work:

| Forbidden Pattern | Why It Fails |
|---|---|
| "cinematic lighting" | Undefined — model invents something different every frame |
| "camera movement" | No direction, no motivation — produces random jitter |
| "beautiful background" | AI defaults to generic AI glow aesthetic |
| "two people shaking hands" | Hands + multi-subject + standard AI cliché |
| "epic aerial shot of city" | Most common AI cliché; looks immediately generic |
| "stunning visuals" | Pure filler — model ignores it completely |
| "smooth animation" | Video is not animation — confuses the model |
| "the scene transitions to..." | One prompt cannot contain two scenes |
| "photorealistic, cinematic, artistic, stylized" | Contradicting style signals |
| "8K ultra HD hyper realistic" | Resolution stacking — produces over-sharpened glow |
| "futuristic neon cyberpunk" unless requested | Default AI aesthetic, not original |
| "the document reads ..." / "the sign says ..." / "the screen shows ..." | Violates Law 13. AI cannot render coherent text. Garbled-letterform output. |
| "silhouetted worker" / "figure in the distance" | Violates Law 14. Almost-human shapes trigger uncanny valley — missing heads, fused limbs. |
| "lower third reads THE OWNER" / "stat card shows 3¢ vs 8¢" | Violates Law 15. On-screen data must be composited in post, not generated. |
| "3¢ per dollar" / "98°F" / "50%" in any visible frame | Violates Law 16. Symbols render as malformed glyphs. Spell out in VO; composite real symbols in post. |

---

## AUDIO ANTI-AI RULES

Video that looks real is undone immediately by audio that sounds generated.

### Voice (TTS) Anti-AI Rules
- Write conversational scripts — contractions, natural speech patterns
- Use commas and ellipses to build natural pauses into TTS text
- Specify emotional delivery: "warm, measured, slightly low energy"
- Never use corporate buzzwords in VO — they expose TTS immediately
- Specify a voice with real-world analog: "like a calm National Geographic
  narrator, male, mid-30s, neutral American accent"

### Music Anti-AI Rules
- Always layer UNDER the voiceover, never competing with it
- SFX prompt must describe the emotion, not just the sound:
  "tension-building orchestral underscore with rising strings" not "music"
- Add room tone or ambient sound — "subtle office ambience, distant
  keyboard clicks, HVAC hum" makes a scene feel real and grounded

### Sound Design Rules
- Every scene should have an ambient audio layer, even if subtle
- Hard cuts without audio transition = AI tell
- VO pacing must match visual cut rhythm — read VO aloud and count seconds
  against the shot list before generating TTS

---

## QUICK REFERENCE — ANTI-AI PROMPT CHECKLIST

Before finalizing any Runway prompt, verify:

```
[ ] Uses I2V (image reference attached)
[ ] Single light source named and directional
[ ] Style token appended verbatim
[ ] Camera body and lens specified
[ ] Film grain included
[ ] One action only
[ ] Hands not in close frame
[ ] No wide shot with multiple small figures
[ ] Physics described for any physical interaction
[ ] Camera movement is motivated, not random
[ ] No AI cliché scenes
[ ] Style consistent with previous clip prompts
[ ] Clip duration ≤ 6 seconds
[ ] No readable text or documents in frame (Law 13)
[ ] No silhouetted or distant human figures (Law 14)
[ ] All stats / lower-thirds / wordmarks marked for post composite (Law 15)
[ ] No ¢ % ° ® ™ © $ £ € or fractions asked to render — spelled out or post-composited (Law 16)
```
