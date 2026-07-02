---
name: RunwayML Expert
description: >
  Makes Claude a complete expert operator of RunwayML — able to plan, build,
  and execute any video, audio, and image workflow on app.runwayml.com using
  the full feature set: Runway Agent, all generation models (Gen-4.5,
  Gen-4, Gen-3, Aleph, Act-One, Act-Two), all Apps (21 pre-built tools),
  Workflows with every node type (generation, LLM, all utility and audio
  nodes), Stitch, Text to Speech, Text to SFX, Voice Dubbing, Voice
  Isolation, Lip Sync, Generate Speech, Characters, camera controls,
  keyframes, Generative Tools, and the complete camera terminology reference.
  Use whenever asked to operate or advise on RunwayML.
version: "2.0"
updated: "2026-05"
sources:
  - https://help.runwayml.com/hc/en-us/categories/1500001930562-Creating-with-Runway
  - https://academy.runwayml.com
  - https://runwayml.com/changelog
  - https://docs.dev.runwayml.com/api-details/api_changelog/
---

# RunwayML Expert Skill

**Version:** 2.0 — May 2026 (built from full help.runwayml.com audit)
**Purpose:** Complete operating manual for Claude when working inside Runway
via Claude in Chrome, or advising on any Runway feature.

---

## 1. PLATFORM OVERVIEW

RunwayML (app.runwayml.com) is a cloud-based AI creative suite for
generating and editing video, image, and audio. Browser-based — no install.
Billed in credits that expire monthly.

**Four main working areas:**
- **Agent** — Conversational multi-shot video production with timeline editor
- **Apps** — 21+ pre-built single-tool interfaces for specific tasks
- **Workflows** — Node-based canvas to chain models into automated pipelines
- **Custom / Sessions** — Direct model access with full settings control

**Account tiers (2026):**

| Plan | Credits/Month | Notes |
|---|---|---|
| Free | 125 one-time | Watermarked, no Gen-4 video |
| Standard | 625 | Credits expire monthly |
| Pro | 2,250 | Custom voices, more features |
| Unlimited | 2,250 + relaxed | Explore Mode, throttle-free |

Credits expire monthly. Failed generations still consume credits.

---

## 1a. INFINITY TOGGLE, STANDING RULE (premium account)

**Rule:** Before generating any clip, **check every node on the canvas for the
infinity (∞) toggle and turn it ON wherever it appears.** It is OFF by default.

**Why:** Our premium Runway plan allows unlimited free generations on certain
models when the per-node infinity toggle is enabled. Leaving the toggle off
silently bills against the monthly credit pool even when the model is eligible
for unlimited use. Over a 6–12 clip production this is the difference between
"~750 credits" and "0 credits" against the pool.

**How to check (every single time):**
1. After dragging a model node onto the canvas, look at the **lower-left
   corner of the node** for the ∞ symbol. Not every model exposes it —
   eligibility is model-by-model on the premium plan.
2. If the ∞ symbol is present in the lower-left, click it so it lights up /
   shows enabled state.
3. Confirm the node's cost label changes to "0 credits" / "unlimited" before
   queuing the run. If the cost label still shows a credit number, the toggle
   is OFF or the model is not eligible.
4. Repeat for every node — toggles do not propagate across the canvas.

**Treat as a gating QA item.** No clip generation is approved until the
toggles are visually confirmed enabled on every eligible node in screenshots
sent to Joseph.

**Mandatory line in every workflow plan:** "STEP 0 — INFINITY TOGGLE PASS:
walk every node on the canvas, enable ∞ where present, confirm 0-credit
billing label, screenshot, send to Joseph for sign-off."

**Mandatory line in every QA checklist:** "[ ] Infinity (∞) toggle enabled
on every eligible node — visually confirmed in canvas screenshot."

---

## 2. RUNWAY AGENT

Runway Agent is a conversational AI creative partner that produces complete
multi-shot videos end-to-end through natural language prompting.

**Access:** Left sidebar Agent icon.

**Workflow (5 steps):**
1. Describe your video in the "Describe your video..." field — subject,
   setting, key actions, narrative arc. Simple sentences work well.
   Optionally add reference images and select a tone.
2. Configure settings: Aspect ratio, Duration (15s or 30s), Resolution
   (720p or 1080p), Audio mode.
3. Click "Create my outline" — review the shot-by-shot plan Agent generates.
   Provide feedback through chat or manually update summary, visual
   references, and story beats before approving.
4. Approve outline — Agent generates each shot, edits them together, and
   adds sound.
5. Touch up in the built-in timeline editor: split clips, trim, adjust
   track volume, add a new media track, undo/redo edits.

**Settings:**
- Aspect ratios: 16:9, 9:16, 1:1
- Duration: 15s or 30s
- Resolution: 720p or 1080p
- Audio modes: Music + Dialogue, Music + Voiceover, Music only

**Credit costs:**

| Resolution | 15s | 30s |
|---|---|---|
| 720p | 540 video + 8-14 audio | 1080 video + 8-14 audio |
| 1080p | 600 video + 8-14 audio | 1200 video + 8-14 audio |
| Per new image created | 20 credits each | |

**Use Agent when:** You want a complete 15-30 second polished video with
sound from one prompt without manually building a Workflow.

---

## 3. VIDEO GENERATION MODELS

### Gen-4.5 (Flagship — Text to Video / Image to Video)
- State-of-the-art motion quality, prompt adherence, visual fidelity
- Understands complex sequenced instructions: camera choreography,
  intricate compositions, precise event timing, atmospheric changes
- **Text to Video spec:**
  - Plan: Standard+
  - Cost: 12 credits/second
  - Duration: 2-10 seconds
  - Aspect ratio: 16:9 ONLY (1280x720)
  - FPS: 24fps or 25fps
  - Explore Mode: Yes
- **Image to Video spec:**
  - All aspect ratios: 16:9, 9:16, 1:1, 4:3, 3:4, 21:9
  - Same cost and duration range
- **Tip:** Image-to-video prompts focus on motion; Text-to-video prompts
  describe both visual elements and motion.
- **Access:** Apps search "Gen-4.5" or from model selector > Video > Gen-4.5

### Gen-4 Video (Controllable, image-required)
- Fast, controllable, production-ready; sits beside live action and VFX
- **Requires an input image** — image is the first frame and visual anchor
- Prompt focuses almost entirely on describing desired motion
- **Gen-4 spec:** 12 credits/sec, 5s or 10s durations, 24fps, 6 aspect ratios
- **Gen-4 Turbo spec:** 5 credits/sec, 5s or 10s durations, 24fps, same ratios
- Explore Mode: Yes (Unlimited plans)
- Platform: Web + iOS
- **Tip:** Test in Turbo first, switch to Gen-4 only when needed

### Aleph (Natural-language video editing)
- Edits and manipulates existing footage using text prompts
- Action verb + transformation: "Add ice spreading over the hand",
  "Change camera to wide angle", "Re-light to winter"
- Can use an input image to influence color, style, lighting
- **Spec:** 15 credits/sec, max 5 seconds, auto-crops unsupported resolutions
- All aspect ratios: 16:9, 9:16, 1:1, 4:3, 3:4, 21:9
- Explore Mode: Yes (Standard+)
- **Access:** Apps > Video > Edit Video

### Gen-3 Alpha
- 10 credits/second
- First frame, last frame, or both keyframes supported
- Video-to-Video up to 20 seconds
- Restyle Video using a reference image
- Advanced Camera Control (direction + intensity)
- 4K upscale available directly inside tool
- Handheld shake and speed control via Edit Video
- Best for: precision camera control, proven cinematic output

### Gen-3 Alpha Turbo
- 5 credits/second, ~7x faster than Alpha
- Requires an input image
- Advanced Camera Control supported
- Best for: rapid iteration, blocking

### Act-One (Performance Capture)
- Animates a character image using facial/body motion from a performance video
- Supports vertical video
- Can transpose performances onto characters inside existing videos
- Input: performance video + target character image
- Best for: facial animation, talking heads, character performance

### Act-Two (Advanced Motion Capture)
- Next-generation motion capture — major improvement over Act-One
- Voice change directly from within the interface
- Input: performance video + character image
- Available via API for integration

### Kling O3 Pro 3.0 / Kling O3 Standard (Third-party)
- Text/Image/Video to Video (third-party via Runway)
- Powers Multi-Shot Video App (Kling Pro 3.0)
- Stronger on physics and long-clip coherence vs Runway native models
- Available as Workflow nodes

### Google Veo 3.1 (Third-party via API/Workflow)
- Text to Image and Image to Video
- First and last keyframe support, 1080p output
- Reference to Video feature

---

## 4. IMAGE GENERATION MODELS

### Frames (Unlimited/Enterprise)
- Most advanced Runway image model — stylistic control and visual fidelity
- Convert reference images to text prompts or Custom Styles
- Best for: concept art, storyboards, style anchors for video

### Gen-4 Image / Gen-4 Image Turbo
- Multimodal: text and/or reference images
- Turbo: generates in ~10 seconds, 2.5-4x cheaper, 93.3% quality score
- Available as Workflow node and standalone App

### GPT Image 2 (Third-party — best for in-image text)
- Exceptional text rendering — use for mockups, posters, signage, social ads
- Supports up to 16 reference images + sketch input
- Aspect ratios: 10 options from 21:9 to 9:16
- Resolutions: 1K, 2K, 4K
- **Credit table (per image):**

| Resolution | Low | Medium | High |
|---|---|---|---|
| 1K & 2K | 1 | 5 | 20 |
| 4K | 2 | 11 | 41 |

- Access: Custom > Image mode > model picker > GPT Image 2
- Explore Mode: Yes

### Magnific Precision v2 (Third-party — image upscaling)
- High-control upscaling — no prompt needed, just upload image
- Settings: Flavor, Scale, Sharpness, Smart grain, Ultra detail
- Access: Custom > Image mode > search "Precision v2"
- Best for: photographers, illustrators, production teams

### Seedance 2.0 (Third-party — multimodal video)
- Generates video from text, reference images, audio, and video inputs
- Director-level control over camera movement, lighting, performance
- Produces audio-visual output with synchronized sound
- **Three creation modes:**
  - References: Blend elements from multiple images/videos with granular
    control over what's pulled from each input
  - Start/End frames: Traditional image-to-video or keyframe control
  - Text to Video: No image input needed; good for realistic human subjects
- Duration: 5-15 seconds
- Resolutions: 480p, 720p, 1080p (1080p = Credits Mode only, no Explore)
- Aspect ratios: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16
- Max inputs: 9 reference images, 3 reference videos (total under 15s)
- Processing time: 2-10 minutes per generation
- Plan: Standard+

### Nano Banana 2 / Grok Imagine (Third-party)
- Text/Image to Image — available in Workflow node library
- Useful for alternative aesthetic styles

---

## 5. AUDIO MODELS

### A. Workflow Audio Nodes (launched November 2025 — paid plans)

#### Text to Speech (TTS)
- ElevenLabs Multilingual v2
- Natural, emotionally-aware speech in 29 languages
- Up to 10,000 characters per run
- Custom Voice requires explicit user consent to create (300 credits)
- **Input:** Text; **Output:** Audio file

#### Text to SFX (Sound Effects)
- ElevenLabs-powered
- Descriptive text to any sound effect
- Examples: "thunderstorm", "laser blast", "busy cafe ambience", "metal clang"
- **Input:** Text; **Output:** Audio file

#### Voice Dubbing
- Translate video dialogue into 29 languages
- Maintains speaker's original voice + emotional tone
- **Input:** Video with audio; **Output:** Dubbed video

#### Voice Isolation
- Strip background noise; isolate crisp clear speech
- Built for film, podcast, and interview workflows
- **Input:** Video or audio; **Output:** Isolated voice audio

### B. Generative Audio (Standalone Dashboard Tools)

#### Lip Sync
- Animate a photo or video with Text to Speech or uploaded audio
- Supports up to 4 faces per video, up to 10 dialogue segments
- 5 credits/second of video output; max 40s per dialogue
- Text character limit: 600 per dialogue
- Supports Multi-Face Lip Sync — assign each dialogue to a different face
- Best practices: human faces only (Act-Two for non-human), forward-facing,
  framed from shoulders up, photorealistic, minimal movement
- Note: Act-Two significantly expands on Lip Sync — prefer Act-Two when
  a driving performance video is available

#### Generate Speech
- Standalone text-to-speech tool (not a Workflow node)
- Access: Generate Audio > type script > select voice > Generate
- Supports preset and custom voices

#### How to Create a Custom Voice
- 300 credits to create
- Describe the voice you want > Generate > preview > name > Add Voice
- Processing: 2-5 minutes
- Available in Lip Sync, Character Script to Video, etc.

---

## 6. RUNWAY CHARACTERS

Real-time conversational AI avatars powered by GWM-1.

**Platform tiers:**

| Context | Max Duration | Cost | Notes |
|---|---|---|---|
| Web App | 2 minutes | 2 credits/6 seconds | Demo/testing |
| Developer Platform | 5 minutes | Same | Custom settings |
| API Integration | 30 minutes | Same | Production |

**Creating a character:**
1. Access: Left sidebar Live icon > Create a Character
2. Upload a character image (forward-facing, shoulders up, simple background,
   no obstructions, no multiple people, horizontal aspect ratio preferred)
3. Select or generate a voice (Preset or Custom — 300 credits to create)
4. Write Instructions: persona, tone, speech patterns, expertise domain,
   emotional guardrails, how character interacts with user
5. Click Create Character (processes 2-5 minutes)

**Chatting:** Browser requests mic (required) and camera (optional). 
Conversation limited to 2 min on web. Can download as video or transcript.

**Character Script to Video App (separate):** For scripted performances from
a character image — uses a preset or custom voice — does NOT require a
live conversation.

---

## 7. GENERATIVE TOOLS (Standalone Tools)

### Remove Background
- AI background removal from video
- Access: Apps > search "Remove Background" or via Gen-3 Alpha Edit Video

### Inpainting (Legacy — use Aleph instead)
- Brush-paint a mask over objects to remove them from video
- Runway now recommends Gen-4 Image References or Aleph for adjustments
- 3-step workflow: Import clip > paint mask > Export Inpaint

### Extract Depth
- Extracts a depth map from a video — used for VFX compositing workflows

### Motion Tracking
- Track a point in a video to attach elements to moving subjects

### Remove Background
- Strip video background entirely for compositing

### Super-Slow Motion
- Available in Video Editor Projects
- Convert footage to high-frame-rate slow motion

---

## 8. ALL 21 APPS (Complete Reference)

Navigate: Left sidebar Apps icon. Use search or browse by category.
Apps are pre-built pipelines for specific creative tasks.

**Video Apps:**

| App | What It Does | Key Inputs |
|---|---|---|
| **Stitch Videos** | Combine multiple clips into one file up to 60 min | 2+ video clips |
| **Multi-Shot Video** | Generate up to 5 connected shots from one prompt (Kling Pro 3.0) | Text prompt, optional first image |
| **Scene Builder** | Two-stage: frame a scene (image), then animate it (video) | Text prompt, optional refs |
| **Character Script to Video** | Animate a character image with dialogue via TTS or audio | Character image + script/voice |
| **Performance Capture with Act-Two** | Motion capture from performance video onto character | Performance video + character image |
| **Product Shot Video Builder** | Generate product videos from a product image | Product image + text |
| **Expand Image** | Extend an image's canvas outward to add new context | Image + desired expansion direction |

**Image Apps:**

| App | What It Does | Key Inputs |
|---|---|---|
| **Upscale Image** | Enhance image resolution | Image |
| **Panel Upscaler** | Upscale panels/storyboards | Image panels |
| **Story Panels** | Expand an image's world with new perspectives | Image + prompt |
| **Runway Look** | Apply a consistent visual style to images | Image + style reference |
| **Mockup** | Place product into lifestyle scene | Product image + scene description |
| **Vary Image** | Generate variations of an existing image | Image |
| **Product Reshoot** | Reshoot product in new context/background | Product image |
| **Stylize Image** | Apply artistic style to an image | Image + style prompt |
| **Character Renderer** | Render a character in different poses/contexts | Character ref + prompt |

**Ad/Creative Apps:**

| App | What It Does | Key Inputs |
|---|---|---|
| **Create Ad** | Generate ad creative from product/brand assets | Image + brief |
| **Vary Ad** | Create variations of existing ad creative | Existing ad image |
| **Ad Concepter** | Generate conceptual ad directions | Brief/prompt |
| **Cinematic Brainstorm** | Generate alternative visual concepts for a scene | Image/prompt |

---

## 9. WORKFLOWS — COMPLETE NODE REFERENCE

The Workflow canvas is a node-based system. Right-click or use "+" to add
nodes. Connect OUTPUT dots (right side) to INPUT dots (left side).
Only compatible types connect: Text-Text, Image-Image, Video-Video, Audio-Audio.

### Canvas Controls

| Action | How |
|---|---|
| Add node | "+" in left panel or right-click canvas |
| Move node | Drag title bar |
| Delete | Select > Backspace |
| Connect | Drag output dot to input dot |
| Rename | "..." > Edit name |
| Lock node | "..." > Lock node (prevents re-run) |
| Duplicate | "..." > Duplicate |
| Select multiple | Shift + click-drag |
| Batch edit settings | Select multiple > bottom toolbar |
| Pan canvas | Click-drag empty space |
| Fit to screen | ⊞ button in bottom toolbar |
| Zoom | Cmd+= / Cmd+- |
| Run all | "Run all" top-right (goes bright white when valid) |
| Run single node | Node's own "Run" button |
| Parallel runs | View/cancel in Active runs panel |

---

### A. INPUT NODES

| Node | Output | Description |
|---|---|---|
| Text | Text | Type any prompt or static value |
| Image | Image | Upload or select from Assets |
| Video | Video | Upload or select from Assets |
| Audio | Audio | Upload or select audio file |
| User Input | Text | Creates an interactive prompt field for Workflow users/App consumers |

---

### B. LLM NODES (AI Prompt Engineering)

Dynamically generate or transform text before it reaches generation models.
Uses credits.

**Available LLM models in Runway (2026):**
- Claude Opus 4.5 — best for complex reasoning and multi-step generation
- Gemini 2.5 Flash — fast and capable
- Nano Banana (Gemini variant)

**System prompt field:** Configure in the gear icon settings panel.

**Key use case — AI Storyboard Generator:**
LLM system prompt:
```
Design a scene storyboard using image prompts. Use the user input to
drive the plot. Use this JSON format:
{ scene: array<{title: string, prompt: string}> }
```
Then connect output to JSON Parse node and extract scene.0.prompt,
scene.1.prompt, scene.0.title, etc. to route each scene to its own
image or video generation node.

---

### C. MEDIA MODEL NODES (Generation — consume credits)

**Video:** Gen-4.5 Video, Gen-4.5 (Text+Image), Gen-4 Video, Gen-4 Turbo,
Gen-3 Alpha, Gen-3 Alpha Turbo, Kling O3 4K, Kling O3 Pro, Kling O3
Standard, Google Veo 3.1

**Image:** Gen-4 Image, Gen-4 Image Turbo, Frames, Nano Banana 2, Grok Imagine

**Audio:** Text to Speech, Text to SFX, Voice Dubbing, Voice Isolation

**Editing/Transform:** Aleph, Act-One, Act-Two

---

### D. UTILITY NODES — AUDIO

#### Extract Audio
Pulls the audio track from a video as a standalone audio file.
- **Input:** Video | **Output:** Audio
- Use: Pull audio from a clip to reuse across scenes, or isolate dialogue.
- How: Link Video → Extract Audio input → Run → Audio output ready.

#### Add Audio
Combines a video with audio, replacing the original audio track.
- **Input:** Video + Audio | **Output:** Video (with new audio)
- Use: Attach TTS voiceover, SFX, or uploaded music to a generated clip.
- How: Link Video → video input, Audio → audio input → Run.
- **This is the key node for full AV production pipelines.**

---

### E. UTILITY NODES — VIDEO

#### Stitch
Combines multiple video inputs into one continuous sequence in order.
- **Input:** Video (multiple) | **Output:** Single merged video
- Order: Input 1 plays first, Input 2 second, etc.
- Add inputs via the "+" button on the node.
- Use: Building a 30-second ad from six 5-second Gen-4.5 clips.
- Note: Stitch also exists as a standalone App (up to 60 minutes total).

#### Trim Video
Shortens a video to a specified duration (shorter than original).
- **Input:** Video | **Output:** Trimmed video
- Use: Cut to exact social media specs (15s Reels, 60s YouTube Shorts).

#### Reverse Video
Plays video and audio backwards from end to start.
- **Input:** Video | **Output:** Reversed video
- Use: Rewind effects, time-reversal sequences, creative transitions.

#### Retime
Speeds up or slows down video by a multiplier.
- **Input:** Video | **Output:** Video at new speed
- Multiplier: 2.0 = double speed, 0.5 = half speed (slow motion)
- Use: Slow-motion for dramatic moments, time-lapses, duration matching.

#### Update FPS
Changes frame rate; applies basic frame interpolation when targeting higher
FPS than source.
- **Input:** Video | **Output:** Video at new FPS
- Use: Standardize FPS across clips before Stitch, or smooth playback.

#### Resize
Changes pixel dimensions (200-4096 per side).
- **Input:** Video | **Output:** Video at new dimensions
- Fit modes: **Contain** (letterbox), **Cover** (crop edges), **Fill**
  (stretch, ignores aspect ratio)
- Use: Meet platform delivery specs, standardize before Stitch.

#### Crop Aspect Ratio
Crops video to a specified aspect ratio with position control.
- **Input:** Video | **Output:** Cropped video
- Position: Left/Right when source is wider than target; Top/Bottom when taller.
- Use: Reformat 16:9 landscape to 9:16 portrait for Reels/TikTok.

#### Upscale Video
Upscales video to 4K resolution.
- **Input:** Video | **Output:** 4K video
- Cost: ~2 credits/second

---

### F. UTILITY NODES — IMAGE

#### Extract Frame
Extracts a specific frame from a video as a high-quality image.
- **Input:** Video | **Output:** Image
- After running, scrub preview to select the exact frame.
- Use: Hero moments for thumbnails, marketing assets, generation inputs.

#### First Frame
Automatically extracts the opening frame from a video as an image.
- **Input:** Video | **Output:** Image
- Use: Verify first frame reference applied correctly; anchor for variations.

#### Last Frame
Automatically extracts the final frame from a video as an image.
- **Input:** Video | **Output:** Image
- **Critical continuity pattern:** Feed Last Frame of clip N as First Frame
  input of clip N+1 for seamless scene-to-scene visual continuity.

#### Segment Image
Extracts specific objects from an image based on a text prompt.
- **Input:** Image + Text description | **Output:** Isolated element image
- After running, click "Edit Segments" to see elements highlighted in purple.
- Use "Exclude from Mask" to remove unwanted masked areas.
- Use "Isolate Mask" dropdown to narrow to single object.
- Click Run again after refining to export final isolated image.
- Use: Subject isolation for compositing, extracting props, pulling assets.

---

### G. PARSE/DATA NODES

#### JSON Parse
Extracts up to 12 values from structured JSON text (from LLM nodes).
- **Input:** Text (JSON) | **Output:** Up to 12 Text outputs
- Path syntax: dot notation, arrays indexed from 0
  - `scene.0.prompt` = first item in `scene` array, `prompt` field
  - `shots.2.camera` = third item in `shots` array, `camera` field
- Hover output dots to preview extracted values before running downstream.

#### Combine Text
Merges multiple text inputs into one text output.
- Use: Combine base style prompt + scene-specific prompt before generation.

---

## 10. COMPLETE WORKFLOW RECIPES

### Recipe 1: 30-Second Advertisement (6 clips × 5s + full audio)
```
[Text: Scene 1 prompt] → [Gen-4.5 Video] ─┐
[Text: Scene 2 prompt] → [Gen-4.5 Video] ─┤
[Text: Scene 3 prompt] → [Gen-4.5 Video] ─┼→ [Stitch] → [Add Audio] → Final
[Text: Scene 4 prompt] → [Gen-4.5 Video] ─┤              ↑
[Text: Scene 5 prompt] → [Gen-4.5 Video] ─┤   [Text to Speech] ──────┤
[Text: Scene 6 prompt] → [Gen-4.5 Video] ─┘   [Text to SFX] ─────────┘
```

### Recipe 2: Consistent Character Multi-Scene (Last Frame Chaining)
```
[Character ref image] ────────────────────────────────────────────┐
[Text: Scene 1] → [Gen-4.5 Turbo: first frame=ref] → [Last Frame] ┘
                                                            ↓
[Text: Scene 2] → [Gen-4.5 Turbo: first frame=↑] → [Last Frame]
                                                         ↓
[Text: Scene 3] → [Gen-4.5 Turbo: first frame=↑]
                                                         ↓
               All three video outputs → [Stitch] → Final video
```

### Recipe 3: AI Storyboard Generator (LLM-driven)
```
[User Input: story concept]
  → [LLM: Claude Opus 4.5 with JSON storyboard system prompt]
  → [JSON Parse]
        → scene.0.prompt → [Gen-4 Image 1]
        → scene.1.prompt → [Gen-4 Image 2]
        → scene.2.prompt → [Gen-4 Image 3]
        → scene.3.prompt → [Gen-4 Image 4]
        → scene.0.title  → [Text label]
```

### Recipe 4: Dubbed Video
```
[Upload: original video with dialogue]
  → [Voice Isolation] → clean voice audio
  → [Voice Dubbing: target="Spanish"] → dubbed audio
  → [Add Audio to original video visuals] → final dubbed video
```

### Recipe 5: Product Demo (4K delivery)
```
[Product image]
[Text: "rotating on white surface, studio lighting"] → [Gen-4.5 Turbo]
[Text: "extreme close-up of product detail"]         → [Gen-4.5 Turbo]
[Text: "lifestyle use scene, kitchen setting"]       → [Gen-4.5 Turbo]
       ↓ all three outputs
[Stitch] → [Upscale Video 4K] → [Crop Aspect Ratio: 16:9]
       ↓
[Text: "upbeat brand music"] → [Text to SFX] → [Add Audio] → Final MP4
```

### Recipe 6: Slow-Motion Dramatic Reveal
```
[Text: "eagle landing on branch, photorealistic"] → [Gen-4.5 Video]
  → [Retime: 0.25x] → [Update FPS: 60] → [Trim Video: 8s] → Final
```

### Recipe 7: Social Reformat Pipeline
```
[16:9 video output] → [Crop Aspect Ratio: 9:16]  → Reels/TikTok
                    → [Crop Aspect Ratio: 1:1]   → Instagram post
                    → [Resize: 1080x1920] → [Update FPS: 30] → Export
```

### Recipe 8: Aleph Edit + Extend
```
[Upload: raw interview footage]
  → [Voice Isolation] → clean audio
  → [Aleph: "Re-light the scene to golden hour"] → improved video
  → [Add Audio: clean audio back] → Final polished clip
```

---

## 11. PROMPT ENGINEERING

### Text-to-Video Formula
```
[Subject + action] in [environment], [lighting], [camera movement],
[style/mood], [technical specs]
```

**Strong example:**
> "A confident business advisor in a navy suit walks through a glass-walled
> Houston boardroom, morning sunlight streaming through floor-to-ceiling
> windows, cinematic dolly shot moving left, photorealistic, 4K, shallow
> depth of field"

### Core Prompt Elements (Per Official Runway Docs)
**Visual components:** subject appearance, environment, lighting,
composition/framing, style

**Motion components:** subject action, environmental motion, camera motion,
motion style and timing, direction and speed

### Best Practices
- Use **positive phrasing** — describe what you want, not what to avoid
- Avoid **ambiguous or conceptual language** ("beautiful", "cool")
- Avoid **conflicting instructions** (e.g., "fast motion" + "slow pan")
- Iteration is expected — generate, review, refine; don't expect perfection
- For Image-to-Video: focus prompt on motion only (image carries visuals)
- For Text-to-Video: describe both visual elements AND motion

### Prompt Qualifiers Library

**Camera movement:** slow zoom in/out, dolly left/right, push in, pull back,
tracking shot, aerial drone descending, handheld shake, pan left/right,
tilt up/down, crane up/down, orbit, arc, whip pan, crash zoom, steadicam,
gimbal, static

**Lighting:** golden hour, magic hour, blue hour, dim amber, cinematic
low-key, bright natural daylight, studio three-point lighting, rembrandt
lighting, moody blue night, neon-lit, rim light, backlit, overcast diffused

**Style:** photorealistic, cinematic, hyperrealistic, 4K, 8K, film grain,
shallow depth of field, bokeh, tack sharp, documentary style, commercial
style, music video style

**Don'ts:** No named brands/logos, no vague prompts, no competing subjects
in one clip, do not describe the edit (describe what the camera sees).
Append "no text, no watermarks" for clean plates.

---

## 12. CAMERA TERMINOLOGY FULL REFERENCE

### Shot Sizes and Framing

| Term | Description |
|---|---|
| Macro | Detailed close-up of something small; makes it feel large |
| Extreme Close Up (ECU) | Shows only a small detail — just eyes, a specific feature |
| Close Up (CU) | Focuses tightly on subject's face or an object |
| Medium | Shows from waist up |
| Full | Shows entire subject from head to toe |
| Wide | Subject and surroundings; full body visible |
| Extreme Wide | Vast area — landscapes or scale |
| Establishing | Sets the scene by showing the location or environment |

### Camera Angles

| Term | Description |
|---|---|
| Aerial | Shot from high in the air — drone or helicopter |
| High angle | Camera looks down on subject from above |
| Low angle | Camera looks up at subject from below |
| Bird's eye view | Looking straight down from directly above |
| Worm's eye view | Looking up from ground level below |
| Over the Shoulder (OTS) | From behind someone's shoulder, showing what they see |
| POV | Point of view — shows exactly what the character sees |

### Composition Techniques

| Term | Description |
|---|---|
| Leading lines | Lines in scene guide the viewer's eye |
| Frame within frame | Doorways/windows create a frame inside the shot |
| Symmetrical | Balanced, mirrored elements on both sides |
| Negative space | Empty space around subject draws attention to them |

### Camera Movements

| Term | Description |
|---|---|
| Pan | Camera rotates left or right on fixed point |
| Tilt up/down | Camera rotates up or down on fixed point |
| Dolly | Camera moves forward or backward on track |
| Push in | Camera moves closer to subject |
| Pull back | Camera moves away from subject |
| Truck | Camera moves left or right, parallel to subject |
| Tracking | Camera follows alongside moving subject |
| Pedestal | Camera moves straight up or down vertically |
| Crane/Jib | Camera moves up/down on large mechanical arm |
| Orbit | Camera circles completely around subject |
| Arc | Camera moves in curved path around subject |
| Zoom | Lens changes focal length |
| Crash zoom | Very fast, dramatic zoom in or out |
| Whip pan | Extremely fast pan creating motion blur |
| Handheld | Natural shakiness from hand-held camera |
| Steadicam | Stabilized handheld — smooth movement while walking |
| Gimbal | Electronic stabilizer; smooth while moving |
| Static | Camera stays completely still |

### Focus Techniques

| Term | Description |
|---|---|
| Deep focus | Everything from near to far in sharp focus |
| Soft focus | Intentionally blurred/hazy for artistic effect |
| Rack focus | Shifting focus from one subject to another mid-shot |
| Shallow focus | Small area in focus, rest blurred (bokeh) |

---

## 13. CAMERA CONTROL (Gen-3 Alpha / Turbo — Advanced Setting)

Choose direction AND intensity of camera movement before generating.

**Controls:** Horizontal (pan), Vertical (tilt), Zoom (in/out), Roll
(CW/CCW), Crane (up/down), Speed (slow/medium/fast)

**Static checkbox:** Locks camera completely — product reveals, talking heads.

**Handheld shake:** Toggle via Edit Video mode — documentary/naturalistic.

---

## 14. KEYFRAMES (Gen-3 Alpha)

| Mode | Description |
|---|---|
| First frame only | Video evolves from your starting image |
| Last frame only | Video ends on specific image (rare) |
| First + Last | Interpolates between two images — morphs/transitions |
| Middle keyframe | Third anchor mid-clip for more path control |

**Continuity chain for long narratives:**
1. Generate clip 1 with First Frame reference
2. Run Last Frame node on clip 1 output
3. Feed that image as First Frame of clip 2
4. Repeat for all clips — creates visually connected long-form narrative

**Note:** Gen-4 does NOT support keyframes. Gen-3 Alpha only.

---

## 15. PUBLISHING WORKFLOWS

### Publishing as an App
Convert a Workflow into a standalone App that users can run without seeing
the node canvas. Expose specific inputs via User Input nodes. Published
Apps appear in the Apps section.

### Publishing as an Endpoint
Expose a Workflow as a REST API endpoint. Returns outputs programmatically.
Enables external tools, n8n automations, or custom apps to trigger
Runway generations without browser interaction.

---

## 16. CREDIT REFERENCE TABLE

| Task | Credits (approx) |
|---|---|
| Gen-4.5 Video, 5s | ~60 |
| Gen-4.5 Turbo, 5s | ~25 |
| Gen-4 Video, 5s | ~60 |
| Gen-4 Turbo, 5s | ~25 |
| Gen-3 Alpha, 10s | ~100 |
| Gen-3 Alpha Turbo, 5s | ~25 |
| Aleph, 5s | ~75 |
| Gen-4 Image | ~10 |
| Gen-4 Image Turbo | ~3-4 |
| GPT Image 2: 1K/Low | 1 |
| GPT Image 2: 1K/High | 20 |
| GPT Image 2: 4K/High | 41 |
| 4K Upscale, 10s | ~20 |
| Lip Sync, 10s output | ~50 |
| Text to Speech (long) | ~5-15 |
| Text to SFX | ~5 |
| LLM node (Claude) | ~3-8 |
| Voice Dubbing, 30s | ~20-30 |
| Custom Voice creation | 300 |
| Characters web, 6s | 2 |
| Agent 720p/15s | 540 video |
| Agent 1080p/30s | 1200 video |

**Strategy:**
- Test with Turbo first; switch to full-quality only for final pass
- Lock completed nodes ("..." > Lock) to prevent re-runs
- Free Preview passes in Apps cost no credits
- Use Explore Mode on Unlimited plan for unlimited Turbo/Gen-4.5 iterations

---

## 17. WHEN TO USE WHAT

| Goal | Best Tool |
|---|---|
| Complete video from one prompt | Runway Agent |
| Quick 5-10s clip | Apps > Gen-4.5 Video |
| Multi-scene video | Workflows: Gen-4.5 × N + Stitch node |
| Consistent character across scenes | Gen-4.5 Turbo + Last Frame → First Frame chain |
| Motion from actor to character | Kling 3.0 Motion Control or Act-Two |
| Natural language video editing | Aleph |
| AI-written scene prompts | LLM node + JSON Parse in Workflows |
| Voiceover | TTS Workflow node OR Generate Speech tool |
| Background music/ambient sound | Text to SFX Workflow node |
| Sync dialogue to character | Lip Sync or Character Script to Video App |
| Translate/dub video | Voice Dubbing Workflow node |
| Clean up interview audio | Voice Isolation Workflow node |
| Real-time conversational avatar | Characters |
| Image with accurate in-image text | GPT Image 2 |
| Upscale an image | Magnific Precision v2 |
| Upscale video to 4K | Upscale Video node in Workflows |
| Reformat to vertical | Crop Aspect Ratio node |
| Slow motion effect | Retime (0.25x) + Update FPS |
| Quick concept storyboard | Scene Builder App or LLM + JSON Parse Workflow |
| Full AV 30s ad | 6x Gen-4.5 + Stitch + TTS + SFX + Add Audio |
| 5-clip narrative sequence | Multi-Shot Video App (Kling Pro 3.0) |
| Product demo video | Product Shot Video Builder App |
| Ad creative | Create Ad App |
| Combine existing clips | Stitch Videos App (up to 60 min) |

---

## 18. CLAUDE-IN-CHROME OPERATING RULES FOR RUNWAY

When controlling Runway via browser:

1. **Screenshot before every click** — canvas changes constantly
2. **Pan before adding nodes** — nodes spawn at current view center; pan to
   empty space before adding each new pair
3. **Wire immediately after placing** — connect Text → Gen node right after
   both appear, before adding the next pair
4. **Verify with Cmd+A** — shows "Run (N nodes)" confirming wired count
5. **Fit to view before running** — ⊞ button audits the full canvas
6. **"Run all" going bright white = valid chain confirmed**
7. **Monitor % progress** — each node shows 0-100% in its preview area
8. **Lock completed nodes** — "..." > Lock node after a good result
9. **Add Audio last** — build video chain first, add TTS/SFX in parallel,
   finish with Add Audio node combining all tracks
10. **Stitch after all clips complete** — confirm all inputs are done before
    connecting to Stitch, then run Stitch separately
11. **Download per node** — "..." > Download video on each completed node;
    Stitch output downloads the merged file
12. **For the Runway Agent** — use Agent icon in left sidebar, NOT Workflows

---

## 19. KNOWN LIMITATIONS

- Single clip max: 10s (Gen-4.5), ~18s via V2V in Gen-3 Alpha
- Keyframes: Gen-3 Alpha ONLY — Gen-4 does NOT support keyframes
- Character consistency across clips requires Last Frame → First Frame
  chaining or the same reference image on every clip
- Text rendered inside AI video is often inaccurate — add title cards in
  post-production
- Lip Sync: human faces only (use Act-Two for non-human faces)
- Seedance 2.0 1080p: Credits Mode only, no Explore Mode
- Failed generations still consume credits
- Free plan watermarks all output
- Unlimited plan still subject to throttling at extreme volumes
- Aleph: max 5 seconds per generation

---

## 20. RESOURCES

| Resource | URL |
|---|---|
| Help Center | help.runwayml.com |
| Academy | academy.runwayml.com |
| Workflow Library | In-app top of Workflows section |
| Changelog | runwayml.com/changelog |
| API Docs | docs.dev.runwayml.com |
| API Changelog | docs.dev.runwayml.com/api-details/api_changelog |
| Discord | discord.gg/runway |
| MCP Server | github.com/runwayml (search "mcp") |
| Prompting Guides | help.runwayml.com/hc/en-us/sections/47313458960403 |
| Camera Terms | help.runwayml.com/hc/en-us/articles/47313504791059 |

## CIRCUIT BREAKER POINTER (2026-06-11)

All Runway operations follow the external-app circuit breaker in
Video Creation/CLAUDE.md: 3 failed attempts on the same error signature,
stop, log, notify Joseph. No exceptions.
