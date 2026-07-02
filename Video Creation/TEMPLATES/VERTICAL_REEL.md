# TEMPLATE: Vertical Reel / TikTok / YouTube Shorts
## Pattern — do not copy content, reuse structure only

---

## NON-NEGOTIABLE RULES FOR VERTICAL

1. **9:16 ONLY** — Generate natively in 9:16. Never crop a 16:9 video.
   In Runway: every Gen-4.5 node must be set to 9:16 aspect ratio.
2. **Music-forward** — Vertical content is music-first. The audio track
   drives pacing. Write prompts to match the energy of the chosen sound.
3. **First frame stops the scroll** — The very first frame must earn
   attention before the viewer's thumb moves. Hook is visual, not verbal.
4. **Captions always on** — Most Reels are watched muted. Every VO or
   dialogue clip gets burned-in captions.
5. **Cut rhythm** — Cuts land on the beat. Write VO so sentences end
   on natural cut points, not mid-word.
6. **Safe zones** — Keep all text and key visuals in the center 70% of
   the frame. Top 15% and bottom 15% are covered by UI on all platforms.

---

## STRUCTURE — 15-SECOND REEL (3 clips × 5s)

| Time | Beat | Purpose | Shot Type | Audio |
|---|---|---|---|---|
| 0:00-0:03 | SCROLL STOPPER | Visual hook — earn attention | Unexpected ECU or bold motion | Music drop / silence |
| 0:03-0:10 | CORE CONTENT | One idea, demonstrated fast | MCU or detail shot | VO + music |
| 0:10-0:15 | CTA / PAYOFF | Punchline or call to action | Return to subject or text card | VO CTA + music out |

---

## STRUCTURE — 30-SECOND REEL (5-6 clips × 5s)

| Time | Beat | Purpose | Shot Type | Audio |
|---|---|---|---|---|
| 0:00-0:04 | SCROLL STOPPER | Hook — unexpected or bold | ECU or wide motion | Music intro |
| 0:04-0:10 | PROBLEM / SETUP | Context or tension | MS of subject | VO line 1 |
| 0:10-0:18 | CONTENT | Core idea or demonstration | Detail shots | VO lines 2-3 |
| 0:18-0:24 | PAYOFF | Result or transformation | MCU — satisfaction | VO line 4 |
| 0:24-0:28 | CTA | Action instruction | CTA card or MCU | VO CTA |
| 0:28-0:30 | LOGO / TAG | Brand outro | Brand card | Music out |

---

## SCRIPT FORMAT

```
[PROJECT NAME] — [15s/30s] Vertical Reel
Platform: [TikTok / Instagram Reels / YouTube Shorts]
Aspect ratio: 9:16 THROUGHOUT

CLIP 01 (0:00-0:04) — SCROLL STOPPER
VISUAL: [describe what fills the 9:16 frame — subject must dominate]
AUDIO: [music drop / no VO]
CAPTION: none

CLIP 02 (0:04-0:10) — SETUP
VISUAL: [description]
VO: "[line 1 — 12-15 words]"
CAPTION: [exact VO text, centered, high contrast]

[continue for each clip]

MUSIC NOTE: [energy level, genre, BPM feel — e.g., "upbeat trap, 120bpm,
drops on first cut at 0:04"]
```

---

## VERTICAL-SPECIFIC PROMPT RULES

**Frame for 9:16 explicitly in every prompt:**
Do not assume the model will compose for vertical. State it directly.

```
"Vertical 9:16 composition. [Subject] fills the frame from mid-torso up,
centered, with [environment] visible as a blurred background strip. The
composition leaves clear space at top and bottom for captions and UI.
[Rest of prompt]"
```

**Never describe horizontal camera moves in vertical content:**
Pans work in 16:9 because width is the long axis. In 9:16, vertical
movement (tilts, pedestals, push-ins) is far more effective.

**Preferred moves for 9:16:**
- Slow push-in toward subject (vertical emphasis)
- Tilt up or down (reveals along the long axis)
- Static camera, subject moves within frame
- Pedestal up (reveals upward)

**Avoid in 9:16:**
- Pan left/right (wastes the long axis)
- Drone aerial shots (almost never work in vertical)
- Wide establishing shots (too much dead space on sides)

---

## PLATFORM-SPECIFIC REQUIREMENTS

| Platform | Max Duration | Music | Safe Zone | Caption Style |
|---|---|---|---|---|
| TikTok | 60s (optimal 15-30s) | Trending audio if possible | Top/Bottom 15% | Bold, high contrast, center |
| Instagram Reels | 90s (optimal 15-30s) | Original or licensed | Top/Bottom 15% | Bold, accessible |
| YouTube Shorts | 60s | No restrictions | Top/Bottom 12% | Auto-captions or burned |
| Facebook Reels | 60s | Licensed preferred | Top/Bottom 15% | Bold |

---

## RUNWAY WORKFLOW PLAN — 30s REEL (5 clips)

```
Reference image → Gen-4 Image (9:16 aspect, lock visual style)

Text [Clip 01 prompt] → Gen-4.5 Turbo 9:16 (first frame = reference)
Text [Clip 02 prompt] → Gen-4.5 Turbo 9:16 (first frame = Last Frame 01)
Text [Clip 03 prompt] → Gen-4.5 Turbo 9:16 (first frame = Last Frame 02)
Text [Clip 04 prompt] → Gen-4.5 Turbo 9:16 (first frame = reference)
Text [Clip 05 prompt] → Gen-4.5 Video 9:16 (brand card)

All 5 → Stitch
Text [VO] → Text to Speech
Text [music/SFX] → Text to SFX
Stitch + TTS + SFX → Add Audio
```

**NOTE:** Set EVERY Gen-4.5 node to 9:16 — 720x1280px.
Confirm 9:16 in Runway settings before running. This is the most common
error — running 16:9 nodes on a vertical project.

**Credit Estimate:**
- 5 clips × 25 = 125
- Reference image = 10
- Audio = 10
- **Draft total: ~145 credits**
- **Final (Gen-4.5 full): ~345 credits**

---

## DELIVERABLES CHECKLIST

- [ ] 9:16 master (30s, with captions burned in)
- [ ] 9:16 master (30s, clean — no captions)
- [ ] 9:16 15s cut-down (clips 01 + 03 + 05)
- [ ] 1:1 cut (center-crop, for Instagram feed)
