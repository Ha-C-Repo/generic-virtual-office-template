---
name: HyperFrames Local Rendering Engine
description: >
  Complete operating reference for HyperFrames — the local HTML-to-video
  rendering engine used on Windows + GPU machines. Covers skill installation,
  all slash commands (/hyperframes, /hyperframes-cli, /hyperframes-media,
  /hyperframes-registry, /website-to-hyperframes, /gsap), composition
  structure, built-in registry blocks (data-chart, shader-transitions,
  social overlays), local TTS via Piper/Bark, the GSAP headless Chrome
  pattern, lint/preview/render pipeline, and the full hybrid assembly
  workflow with Runway B-roll. Use when orchestrate.js returns
  HYPERFRAMES_LOCAL or HYBRID.
version: "2.0"
updated: "2026-05"
depends_on:
  - RUNWAY.md (for B-roll generation in HYBRID mode)
  - ANTI_AI.md (for Runway prompt rules in HYBRID mode)
---

# HyperFrames Local Rendering Engine

HyperFrames converts plain HTML + CSS + JavaScript into studio-quality MP4
video frames using a headless Chrome instance driven by the local GPU.
Free, offline, no watermarks, no credit costs. Combined with Runway
cinematic B-roll, it produces agency-quality output at $0 assembly cost.

---

## 1. INSTALLATION & SKILL ACTIVATION

```bash
# Install HyperFrames globally
npm install -g hyperframes

# Install project dependencies from video studio root
npm install

# CRITICAL — Activate native Claude slash-command sub-skills
# Run this inside the project folder to unlock /hyperframes, /gsap, etc.
npx skills add heygen-com/hyperframes

# Verify installation
npx hyperframes --version
```

After `npx skills add heygen-com/hyperframes`, Claude gains six native
sub-skills as slash commands. These must be installed once per project folder.

---

## 2. THE SIX SLASH COMMAND SKILLS

### `/hyperframes` — Composition Authoring
Forces Claude to write standard HTML5 structures mapping timeline tracks
and video dimensions onto layout elements using native data attributes:
`data-composition-id`, `data-start`, `data-duration`, `data-track-index`.
Claude writes syntactically correct compositions with proper layer ordering,
timing alignment, and dimension declarations.

**Invoke when:** Writing any new composition HTML file.

### `/hyperframes-cli` — Developer Loop Control
Enables Claude to control the full rendering stack autonomously:
- `npx hyperframes init` — scaffold a new composition project
- `npx hyperframes lint` — inspect timeline bugs (overlaps, caption drift, layer bleed)
- `npx hyperframes preview` — spin up a local hot-reloaded dev server for real-time iteration
- `npx hyperframes render` — export the final MP4 output

**Invoke when:** Running any CLI operation — lint, preview, or render.

### `/hyperframes-media` — Asset Preprocessing
Handles all timeline asset preparation:
- Calls **local TTS engines** (Piper or Bark) to generate voiceover .wav files
  entirely on local hardware — no cloud API, no cost
- Strips background noise from audio
- Generates word-level caption alignment timestamps for subtitle sync
- Preprocesses image assets (resize, format convert) for composition use

**Invoke when:** Generating voiceover audio locally, creating caption timing files.

### `/hyperframes-registry` — Component Installation
Allows Claude to pull pre-verified block structures directly into the
codebase via `npx hyperframes add [component]` — no writing component code
from scratch. All components are open-source, locally rendered, no fees.

Available blocks (see Section 5 for detail):
- `data-chart` — animated data visualization and bar-chart races from CSV
- `instagram-follow` — social media overlay cards
- `lower-thirds` — name/title bugs with brand styling
- `shader-transitions` — 14 WebGL transition shaders
- `progress-bar` — timeline progress indicator
- `countdown-timer` — animated countdown
- `cta-card` — call-to-action overlay

**Invoke when:** Adding any pre-built component to a composition.

### `/website-to-hyperframes` — URL to Video Ingestion
Instructs Claude to scrape a live URL, extract its CSS branding/layout rules,
and convert the core text and visual assets into an automated marketing or
promo video. Captures: brand colors, fonts, hero copy, images, and page
structure — then maps them into a HyperFrames composition automatically.

**Invoke when:** User provides a URL and asks to create a promo video from it.

```
Example: "Make a 30s promo for yourcompany.example.com"
→ Claude invokes /website-to-hyperframes
→ Scrapes site, extracts brand colors, fonts, hero text, logo
→ Builds composition using extracted assets
→ No manual brand input required
```

### `/gsap` — Advanced Motion Architecture
Teaches Claude to structure seekable, pixel-perfect motion paths using the
correct headless Chrome capture pattern. All animations are bound to a
paused master timeline so headless Chrome can scrub frame-by-frame with
zero lag or dropped frames.

**Critical pattern — always use this structure:**
```javascript
// CORRECT for HyperFrames headless capture
const tl = gsap.timeline({ paused: true });
window.__timelines = window.__timelines || [];
window.__timelines.push(tl);

tl.from('#headline', { opacity: 0, y: 40, duration: 0.9, ease: 'power3.out' })
  .from('#eyebrow',  { opacity: 0, y: 20, duration: 0.6 }, '-=0.3')
  .from('#cta',      { opacity: 0, scale: 0.9, duration: 0.5 }, '-=0.2');

// WRONG — do NOT use this in HyperFrames
// gsap.from('#headline', { ... })  // Runs immediately, Chrome can't scrub it
```

**Why this matters:** `window.__timelines` exposes the paused timeline to
HyperFrames' headless Chrome driver, which scrubs it forward frame-by-frame
for perfect capture. Animations NOT in a paused timeline will run at page
load speed and produce blurring, lag, or dropped frames in output.

**Invoke when:** Writing any GSAP animation inside a HyperFrames composition.

---

## 3. STORYBOARD PROFILE — script.json

Before writing any composition HTML, Claude generates a `script.json`
storyboard profile. This maps timecodes, visual hooks, and VO blocks —
the single source of truth that both the Runway prompt list and the
HyperFrames composition pull from.

```json
{
  "project": "Your Company - 30s Ad",
  "engine": "HYBRID",
  "total_duration": 30,
  "style": "Style02_Luxury_Premium",
  "aspect_ratio": "16:9",
  "scenes": [
    {
      "id": "scene-01",
      "timecode_in": "00:00:00",
      "timecode_out": "00:00:05",
      "duration": 5,
      "visual_hook": "ECU of printed contract pages on polished mahogany desk, warm side light",
      "runway_prompt": "Extreme close-up of crisp printed contract pages on a polished mahogany conference table...",
      "runway_clip": "src/shared_assets/runway_scene01_ecu_contract.mp4",
      "hyperframes_layers": [
        { "layer": 1, "type": "video", "src": "runway_scene01_ecu_contract.mp4" },
        { "layer": 2, "type": "gradient_overlay", "style": "navy_left" },
        { "layer": 3, "type": "text", "content": "YOUR COMPANY", "animation": "fade_up", "start": 0.5 }
      ],
      "voiceover": "Most advisors have never run a company.",
      "voiceover_file": "src/shared_assets/vo_scene01.wav",
      "music": "subtle cinematic tension underscore"
    },
    {
      "id": "scene-02",
      "timecode_in": "00:00:05",
      "timecode_out": "00:00:10",
      "duration": 5,
      "visual_hook": "Medium shot of advisor reviewing financial documents, Houston skyline at dusk",
      "runway_prompt": "Medium shot of a composed 50-year-old man in a charcoal suit...",
      "runway_clip": "src/shared_assets/runway_scene02_advisor_desk.mp4",
      "hyperframes_layers": [
        { "layer": 1, "type": "video", "src": "runway_scene02_advisor_desk.mp4" },
        { "layer": 2, "type": "gradient_overlay", "style": "navy_left" },
        { "layer": 3, "type": "lower_third", "name": "The Owner", "title": "CEO, Your Company", "start": 1.2 }
      ],
      "voiceover": "The Owner has operated in Houston for nine years.",
      "voiceover_file": "src/shared_assets/vo_scene02.wav",
      "music": "continues"
    }
  ]
}
```

Save to: `ACTIVE_PROJECTS/[ProjectName]/script.json`

---

## 4. COMPOSITION STRUCTURE (full reference)

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { width: 1920px; height: 1080px; overflow: hidden; background: #000; }
  </style>
</head>
<body>

  <div
    data-composition-id="scene-01-hook"
    data-width="1920"
    data-height="1080"
    data-duration="5"
    data-fps="30"
    data-track-index="0"
    data-audio="../../src/shared_assets/vo_scene01.wav"
    style="position:relative; width:1920px; height:1080px;"
  >
    <!-- Layer 1: Runway B-roll background -->
    <video
      src="../../src/shared_assets/runway_scene01.mp4"
      data-start="0" data-duration="5"
      muted playsinline
      style="position:absolute;top:0;left:0;width:1920px;height:1080px;
             object-fit:cover;z-index:1;"
    ></video>

    <!-- Layer 2: Brand gradient -->
    <div style="position:absolute;inset:0;z-index:2;
      background:linear-gradient(to right,rgba(26,39,68,0.85) 0%,
      rgba(26,39,68,0.3) 55%,transparent 100%);"></div>

    <!-- Layer 3: Animated content -->
    <div id="content-01" style="position:absolute;left:120px;top:50%;
         transform:translateY(-50%);z-index:3;">
      <p id="eyebrow-01" style="font:400 22px/1 'Helvetica Neue',sans-serif;
         color:#B8860B;letter-spacing:7px;text-transform:uppercase;
         margin-bottom:20px;opacity:0;">YOUR COMPANY</p>
      <h1 id="hl-01" style="font:700 68px/1.1 'Helvetica Neue',sans-serif;
         color:#FFF;max-width:750px;opacity:0;">Most advisors have never
      run a company.</h1>
    </div>
  </div>

  <!-- Load GSAP -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
  <script>
    // CORRECT headless Chrome pattern — paused timeline bound to window.__timelines
    window.__timelines = window.__timelines || [];

    const tl01 = gsap.timeline({ paused: true });
    window.__timelines.push(tl01);

    tl01
      .to('#eyebrow-01', { opacity:1, y:0, from:{y:20}, duration:0.7, ease:'power3.out', delay:0.4 })
      .to('#hl-01',      { opacity:1, y:0, from:{y:35}, duration:0.9, ease:'power3.out' }, '-=0.3');
  </script>

</body>
</html>
```

### Data Attributes Reference

| Attribute | Required | Description |
|---|---|---|
| `data-composition-id` | Yes | Unique ID → output filename |
| `data-width` | Yes | Output width in pixels |
| `data-height` | Yes | Output height in pixels |
| `data-duration` | Yes | Scene duration in seconds |
| `data-fps` | No | Frame rate (default: 30) |
| `data-track-index` | No | Scene order for multi-scene files |
| `data-audio` | No | Path to audio file to mix into output |
| `data-audio-offset` | No | Audio start offset in seconds |
| `data-start` (elements) | No | When element enters scene (seconds) |
| `data-end` (elements) | No | When element exits scene (seconds) |

---

## 5. BUILT-IN REGISTRY BLOCKS

Install any block with: `npx hyperframes add [block-name]`
No writing from scratch. All locally rendered. No licensing fees.

### data-chart — Animated Data Visualization
```bash
npx hyperframes add data-chart
```
Converts raw CSV data or JSON arrays into animated graph loops or
bar-chart races. Useful for financial comparisons, performance metrics,
and any data-driven marketing content.

```html
<!-- After installing: inject into composition -->
<div data-component="data-chart"
     data-src="../../src/shared_assets/metrics.csv"
     data-type="bar-race"
     data-duration="5"
     data-color-primary="#B8860B"
     data-color-secondary="#1A2744"
     style="position:absolute;inset:0;z-index:3;">
</div>
```

### shader-transitions — 14 WebGL Transition Shaders
```bash
npx hyperframes add shader-transitions
```
Installs 14 native WebGL transition shaders between scenes. Claude
dynamically recalculates transition timemarkers if scene durations change.

**Available shaders:**

| Shader | Effect | Best for |
|---|---|---|
| `whip-pan` | Extreme fast horizontal blur | Action, energy, fast cuts |
| `glitch` | Digital artifact distortion | Tech, cybersecurity, hype |
| `cross-warp-morph` | Warped cross-dissolve | Brand reveals, transformations |
| `ridged-burn` | Edge burn-out dissolve | Drama, film noir, end cards |
| `fade-black` | Classic cut to black | Scene breaks, chapter starts |
| `fade-white` | Cut to white | Luxury, clean, aspirational |
| `zoom-blur` | Push-in blur transition | Commercial energy, hooks |
| `pixelate` | Pixel dissolve | Tech, retro, social media |
| `page-curl` | Physical page turn | Documentary, editorial |
| `swipe-left` | Hard horizontal wipe | Social, tutorial, how-to |
| `swipe-up` | Vertical wipe upward | Vertical Reels, TikTok |
| `ripple` | Water ripple dissolve | Lifestyle, wellness, beauty |
| `static-burst` | TV static flash | News, urgency, alerts |
| `iris-open` | Circle wipe reveal | Classic cinema, theatrical |

```html
<!-- Apply a transition between scenes -->
<div data-transition="whip-pan"
     data-transition-duration="0.3"
     data-transition-from="scene-01-hook"
     data-transition-to="scene-02-advisor">
</div>
```

### instagram-follow / social-overlay — Social Media Cards
```bash
npx hyperframes add instagram-follow
npx hyperframes add lower-thirds
```
Populates the timeline with clean brand elements:
- Instagram follow prompts with profile avatar and handle
- Name/title lower thirds with brand colors
- Progress bars (story-style)
- Call-to-action cards with URL
- Subscriber count animations

```html
<!-- Lower third (auto-styled to brand colors from .env) -->
<div data-component="lower-thirds"
     data-name="The Owner"
     data-title="CEO, Your Company"
     data-color-bar="#B8860B"
     data-color-bg="rgba(26,39,68,0.92)"
     data-start="1.2"
     data-end="4.5"
     style="position:absolute;bottom:120px;left:0;z-index:10;">
</div>
```

---

## 6. LOCAL TTS — FREE VOICEOVER ON WINDOWS

`/hyperframes-media` invokes local TTS engines to generate voiceover audio
on your GPU without any cloud API or per-character cost.

### Option A — Piper TTS (recommended, fast, GPU-accelerated)
```bash
# Install Piper
pip install piper-tts

# Generate voiceover (invoke via /hyperframes-media)
piper \
  --model en_US-lessac-high \
  --output_file src/shared_assets/vo_scene01.wav \
  <<< "Most advisors have never run a company."

# Batch generate all VO lines from script.json
node -e "
  const script = require('./ACTIVE_PROJECTS/ProjectName/script.json');
  const {execSync} = require('child_process');
  script.scenes.forEach(s => {
    execSync(\`echo '\${s.voiceover}' | piper --model en_US-lessac-high --output_file \${s.voiceover_file}\`);
    console.log('Generated:', s.voiceover_file);
  });
"
```

### Option B — Bark TTS (more expressive, slower, GPU-required)
```bash
# Install Bark
pip install git+https://github.com/suno-ai/bark.git

# Generate with emotion/style control
python -c "
from bark import SAMPLE_RATE, generate_audio, preload_models
from scipy.io.wavfile import write as write_wav
preload_models()
audio = generate_audio('[calm, authoritative] Most advisors have never run a company.')
write_wav('src/shared_assets/vo_scene01.wav', SAMPLE_RATE, audio)
"
```

### Choosing Piper vs Bark

| Factor | Piper | Bark |
|---|---|---|
| Speed | Fast (~1s per sentence) | Slow (10-30s per sentence) |
| Quality | Clear, professional | Highly expressive, natural |
| GPU required | No (CPU fast enough) | Yes (GPU strongly preferred) |
| Emotion control | Limited | Full (via text prompts) |
| Best for | Business narration, clear VO | Character voices, storytelling |

### Caption Alignment (word-level timestamps)
After generating audio, `/hyperframes-media` creates a `.vtt` subtitle file
with word-level timestamps for frame-accurate caption sync:

```bash
# Using whisper for alignment (free, local)
pip install openai-whisper
whisper src/shared_assets/vo_scene01.wav --output_format vtt \
  --output_dir src/shared_assets/ --language en
```

---

## 7. THE DEVELOPER LOOP (/hyperframes-cli)

```bash
# 1. Scaffold a new project
npx hyperframes init

# 2. Lint — check for timeline bugs before rendering
npx hyperframes lint src/hyperframes/MyProject.html
# Reports: caption drift, layer bleed, timeline overlaps, missing audio refs

# 3. Preview — hot-reload dev server (iterate without re-rendering)
npx hyperframes preview src/hyperframes/MyProject.html
# Opens in browser at localhost:3000
# Changes to HTML/CSS/JS update instantly

# 4. Render — final export
npx hyperframes render src/hyperframes/MyProject.html \
  --quality high \
  --fps 30 \
  --output src/shared_assets/rendered/

# Render single scene only
npx hyperframes render src/hyperframes/MyProject.html \
  --id scene-02-advisor \
  --output src/shared_assets/rendered/

# 60fps for slow-motion or high-motion content
npx hyperframes render src/hyperframes/MyProject.html \
  --quality high --fps 60

# Watch mode (auto re-render on save)
npx hyperframes render src/hyperframes/MyProject.html --watch
```

---

## 8. GSAP ADVANCED PATTERNS (headless-safe)

All animations MUST use the `paused: true` + `window.__timelines` pattern.
Never use direct `gsap.from()` / `gsap.to()` calls at page scope.

```javascript
window.__timelines = window.__timelines || [];

// ── PATTERN 1: Staggered text reveal ──────────────────────────────────
const tlText = gsap.timeline({ paused: true });
window.__timelines.push(tlText);
tlText.from('.word', { opacity:0, y:20, stagger:0.06, duration:0.5, ease:'power2.out' });

// ── PATTERN 2: Clip-path horizontal reveal wipe ───────────────────────
const tlWipe = gsap.timeline({ paused: true });
window.__timelines.push(tlWipe);
tlWipe.from('.reveal-block', {
  clipPath: 'inset(0 100% 0 0)',
  duration: 0.9,
  ease: 'power4.inOut'
});

// ── PATTERN 3: Number counter ─────────────────────────────────────────
const tlCount = gsap.timeline({ paused: true });
window.__timelines.push(tlCount);
const obj = { val: 0 };
tlCount.to(obj, {
  val: 9,
  duration: 1.8,
  snap: { val: 0.1 },
  onUpdate: () => { document.getElementById('counter').textContent = obj.val.toFixed(1); }
});

// ── PATTERN 4: SVG line draw ──────────────────────────────────────────
const tlLine = gsap.timeline({ paused: true });
window.__timelines.push(tlLine);
tlLine.from('.accent-line', { strokeDashoffset: 600, duration: 0.7, ease:'power2.out' });

// ── PATTERN 5: Scale pop (logo / badge) ──────────────────────────────
const tlPop = gsap.timeline({ paused: true });
window.__timelines.push(tlPop);
tlPop.from('#logo', { scale:0.6, opacity:0, duration:0.5, ease:'back.out(1.7)' });

// ── PATTERN 6: autoAlpha (prevents Chrome rendering ghost frames) ─────
// Use autoAlpha instead of opacity for elements that start hidden.
// autoAlpha sets visibility:hidden AND opacity:0, preventing Chrome
// from capturing a ghost frame of the element before animation starts.
const tlSafe = gsap.timeline({ paused: true });
window.__timelines.push(tlSafe);
tlSafe.from('#overlay', { autoAlpha:0, y:30, duration:0.8 });
// NOT: opacity:0 alone — this can bleed a transparent frame into render
```

---

## 9. FULL HYBRID WORKFLOW — STEP BY STEP

When `orchestrate.js` returns `HYBRID`:

```
SETUP (one time per project)
  npx skills add heygen-com/hyperframes   ← activate slash skills
  npm install                              ← install dependencies
  Copy .env.template → .env               ← fill in config

STEP 1 — STORYBOARD
  Generate script.json using scene structure above
  Save → ACTIVE_PROJECTS/[ProjectName]/script.json
  This drives both the Runway prompt list AND the HyperFrames composition

STEP 2 — LOCAL TTS (if voiceover needed)
  Invoke /hyperframes-media
  Run Piper for each scene's voiceover text from script.json
  Output: src/shared_assets/vo_scene[N].wav
  Run whisper for caption alignment → src/shared_assets/vo_scene[N].vtt

STEP 3 — RUNWAY B-ROLL GENERATION
  Open Runway in Chrome (Claude in Chrome MCP)
  Build Workflow: 1 Text node + 1 Gen-4.5 Turbo node per scene
  Apply Anti-AI laws to every prompt from script.json runway_prompt fields
  Download outputs → src/shared_assets/runway_scene[N].mp4

STEP 4 — HYPERFRAMES COMPOSITION
  Invoke /hyperframes to write composition HTML
  File: src/hyperframes/[ProjectName].html
  Per scene div:
    data-audio points to the matching vo_scene[N].wav
    Layer 1 (z:1): <video> with matching runway_scene[N].mp4
    Layer 2 (z:2): Brand gradient overlay
    Layer 3 (z:3): GSAP text animations (paused timeline pattern)
    Layer 4 (z:4): Lower thirds via registry block
    Layer 5 (z:5): Logo (end scenes only)
  Add shader transitions between scenes via registry block

STEP 5 — LINT
  Invoke /hyperframes-cli
  npx hyperframes lint src/hyperframes/[ProjectName].html
  Fix any reported timeline overlaps or caption drift

STEP 6 — PREVIEW
  npx hyperframes preview src/hyperframes/[ProjectName].html
  Review at localhost:3000 — adjust timing, wording, animation speeds

STEP 7 — RENDER
  npx hyperframes render src/hyperframes/[ProjectName].html \
    --quality high --fps 30 \
    --output src/shared_assets/rendered/

STEP 8 — STITCH + FINAL MIX (if multiple scenes rendered separately)
  ffmpeg -f concat -safe 0 -i filelist.txt -c copy \
    OUTPUTS/[ProjectName]/final_master.mp4
  OR use Runway Stitch node if already in Runway

STEP 9 — DELIVER
  Copy to OUTPUTS/[ProjectName]/
  Note the Owner's approval required before external release
```

---

## 10. WEBSITE-TO-VIDEO WORKFLOW (/website-to-hyperframes)

```
User: "Make a promo video for yourcompany.example.com"

Claude invokes /website-to-hyperframes:

1. Scrape the URL
   - Extract: brand colors (CSS variables or computed styles)
   - Extract: fonts (Google Fonts links, CSS font-family)
   - Extract: hero heading text
   - Extract: subheadline / value proposition text
   - Extract: logo image URL
   - Extract: CTA text and URL

2. Map to brand tokens
   - Primary color → data-color-primary in registry blocks
   - Font family → font-family in all composition CSS
   - Logo URL → src attribute on logo layer

3. Auto-generate composition structure
   - Scene 1: Hero visual (Runway prompt built from hero text)
   - Scene 2: Value prop (HyperFrames text card with scraped copy)
   - Scene 3: CTA card (registry cta-card block with scraped URL)

4. Output composition HTML to src/hyperframes/[domain]-promo.html
5. Proceed with normal lint → preview → render pipeline
```

---

## 11. COMPOSITION TEMPLATES — READY TO PASTE

### Title Card (5s, navy/gold brand)
```html
<div data-composition-id="title-card" data-width="1920" data-height="1080"
     data-duration="5" data-fps="30"
     style="position:relative;width:1920px;height:1080px;background:#1A2744;">
  <div style="position:absolute;top:0;left:0;width:6px;height:100%;background:#B8860B;z-index:2;"></div>
  <video src="../../src/shared_assets/RUNWAY_CLIP.mp4" muted playsinline
         style="position:absolute;inset:0;width:1920px;height:1080px;object-fit:cover;z-index:1;opacity:0.35;"></video>
  <div style="position:absolute;left:120px;top:50%;transform:translateY(-50%);z-index:3;">
    <p id="eyebrow" style="font:400 22px/1 'Helvetica Neue',sans-serif;
       color:#B8860B;letter-spacing:7px;text-transform:uppercase;margin-bottom:24px;opacity:0;">
       REPLACE EYEBROW</p>
    <h1 id="headline" style="font:700 72px/1.1 'Helvetica Neue',sans-serif;
       color:#FFF;max-width:800px;opacity:0;">REPLACE HEADLINE</h1>
  </div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || [];
    const tl = gsap.timeline({ paused: true });
    window.__timelines.push(tl);
    tl.to('#eyebrow',  { autoAlpha:1, y:0, from:{y:20}, duration:0.7, delay:0.4, ease:'power3.out' })
      .to('#headline', { autoAlpha:1, y:0, from:{y:35}, duration:0.9, ease:'power3.out' }, '-=0.3');
  </script>
</div>
```

### Lower Third Bug
```html
<div id="lower-third"
     style="position:absolute;bottom:120px;left:0;z-index:10;
            display:flex;align-items:stretch;opacity:0;">
  <div style="width:6px;background:#B8860B;flex-shrink:0;"></div>
  <div style="background:rgba(26,39,68,0.92);padding:18px 32px;">
    <p style="font:700 30px/1 'Helvetica Neue',sans-serif;color:#FFF;margin-bottom:8px;">
      REPLACE NAME</p>
    <p style="font:400 18px/1 'Helvetica Neue',sans-serif;color:#B8860B;
       letter-spacing:4px;text-transform:uppercase;">REPLACE TITLE</p>
  </div>
</div>
<script>
  window.__timelines = window.__timelines || [];
  const tlLT = gsap.timeline({ paused: true });
  window.__timelines.push(tlLT);
  tlLT.to('#lower-third', { autoAlpha:1, x:0, from:{x:-250}, duration:0.6, delay:1.2, ease:'power2.out' })
      .to('#lower-third', { autoAlpha:0, duration:0.4, delay:2.5, ease:'power2.in' });
</script>
```

### CTA End Card (5s)
```html
<div data-composition-id="cta-card" data-width="1920" data-height="1080"
     data-duration="5" data-fps="30"
     style="position:relative;width:1920px;height:1080px;background:#1A2744;">
  <div id="rule" style="position:absolute;top:calc(50% - 70px);left:50%;
       width:0;height:1px;background:#B8860B;transform:translateX(-50%);z-index:1;"></div>
  <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
              text-align:center;z-index:2;">
    <!-- TODO: replace src with the actual logo path once the file is
         present at ASSETS/brand/Your Company/your_company.jpg. Until then this
         <img> will 404 at render time — the surrounding text reveal still
         works for testing. See ASSETS/brand/brand_colors.md "ASSET LOGO TODO". -->
    <img id="logo" src="../../ASSETS/brand/Your Company/your_company.jpg"
         style="height:80px;margin-bottom:36px;opacity:0;"
         onerror="this.style.display='none'">
    <p id="url" style="font:400 34px/1 'Helvetica Neue',sans-serif;
       color:#B8860B;letter-spacing:6px;opacity:0;">REPLACE-URL.COM</p>
    <p id="tag" style="font:300 20px/1 'Helvetica Neue',sans-serif;
       color:rgba(255,255,255,0.55);letter-spacing:3px;margin-top:14px;opacity:0;">
       REPLACE TAGLINE</p>
  </div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || [];
    const tl = gsap.timeline({ paused: true });
    window.__timelines.push(tl);
    tl.to('#rule',  { width:400, duration:0.6, ease:'power2.out' })
      .to('#logo',  { autoAlpha:1, duration:0.5 }, '-=0.1')
      .to('#url',   { autoAlpha:1, y:0, from:{y:15}, duration:0.5 }, '-=0.1')
      .to('#tag',   { autoAlpha:1, duration:0.4 }, '-=0.1');
  </script>
</div>
```

---

## 12. FFMPEG ASSEMBLY REFERENCE

```bash
# Create ordered filelist
cat > src/shared_assets/rendered/filelist.txt << 'EOF'
file 'scene-01-hook.mp4'
file 'scene-02-advisor.mp4'
file 'scene-03-proof.mp4'
file 'cta-card.mp4'
EOF

# Stitch scenes only (no audio)
ffmpeg -f concat -safe 0 \
  -i src/shared_assets/rendered/filelist.txt \
  -c copy OUTPUTS/ProjectName/final_video_only.mp4

# Stitch + mix VO + music
ffmpeg -f concat -safe 0 \
  -i src/shared_assets/rendered/filelist.txt \
  -i src/shared_assets/voiceover_full.wav \
  -i src/shared_assets/music_underscore.wav \
  -filter_complex "[1:a][2:a]amix=inputs=2:duration=first:weights=1 0.25[a]" \
  -map 0:v -map "[a]" -shortest \
  OUTPUTS/ProjectName/final_master.mp4

# Reformat to vertical 9:16
ffmpeg -i OUTPUTS/ProjectName/final_master.mp4 \
  -vf "crop=608:1080:(iw-608)/2:0,scale=1080:1920" \
  OUTPUTS/ProjectName/final_9x16.mp4
```

---

## 13. CLAUDE COWORK OPERATING RULES

1. **Always run `node orchestrate.js` first** — confirm HYBRID before starting
2. **Always install slash skills** — `npx skills add heygen-com/hyperframes`
3. **Generate script.json before any HTML** — it's the single source of truth
4. **Use autoAlpha, not opacity** for elements that start hidden in GSAP
5. **All GSAP timelines must be paused + in window.__timelines** — no exceptions
6. **Lint before preview, preview before render** — never skip to render
7. **Runway clips go to shared_assets before HyperFrames composition is written**
8. **Match data-duration exactly to the Runway clip length** for each scene
9. **Use registry blocks instead of hand-writing components** when available
10. **Save renders to src/shared_assets/rendered/, finals to OUTPUTS/**

## CIRCUIT BREAKER POINTER (2026-06-11)

All HyperFrames render and host-app operations follow the external-app
circuit breaker in Video Creation/CLAUDE.md: 3 failed attempts on the same
error signature, stop, log, notify Joseph. Independent animations render
via parallel sub-agents, one per unit.
