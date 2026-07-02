# TEMPLATE: Short Film / Movie Scene
## Pattern — do not copy content, reuse structure only

---

## STRUCTURE ARCHETYPES

### Archetype A — The 3-Act Short (90s-3min)

| Act | Duration | Purpose | Clip Count |
|---|---|---|---|
| Act 1: ESTABLISH | 0:00-0:20 | World, character, tension | 3-4 clips |
| Act 2: CONFRONT | 0:20-1:00 | Conflict, escalation, turning point | 8-10 clips |
| Act 3: RESOLVE | 1:00-1:30 | Resolution, emotional payoff, button | 4-5 clips |

### Archetype B — The Vignette (30-60s, no dialogue)
Pure visual storytelling. No VO. Music and ambient sound only.

| Beat | Duration | Purpose |
|---|---|---|
| WORLD | 0:00-0:10 | Establish location and atmosphere |
| CHARACTER | 0:10-0:25 | Introduce person in their environment |
| ACTION | 0:25-0:45 | One meaningful action or moment |
| RESOLUTION | 0:45-0:60 | Consequence or emotional resonance |

### Archetype C — The Cinematic Sequence (60-90s)
Driven by a voiceover monologue or narration over atmospheric visuals.

| Beat | Duration | Purpose |
|---|---|---|
| OPENING IMAGE | 0:00-0:05 | Arresting visual, no context yet |
| NARRATION BEGINS | 0:05-0:25 | VO establishes the premise |
| TENSION | 0:25-0:50 | VO builds — visuals dramatize |
| TURN | 0:50-1:10 | The insight or revelation |
| CLOSING IMAGE | 1:10-1:30 | Return to opening image or bookend |

---

## SHOT DESIGN RULES FOR NARRATIVE

**Scene Economy:** One new location per 3-4 clips maximum. Reusing
locations (with varied framing) creates coherence.

**Character Continuity Protocol:**
1. Generate reference image for EVERY named character
2. Use that reference as first frame for ALL clips featuring that character
3. Extract Last Frame of each clip — use as First Frame of next clip in
   same location/scene
4. Different location = new reference image for that space

**Pace by Genre:**
- Drama: 6-8s clips, slow deliberate camera
- Thriller/Action: 3-4s clips, dynamic angles
- Documentary: 6-8s clips, handheld, observational
- Commercial/Branded: 4-5s clips, motivated camera

---

## DIALOGUE HANDLING

AI video cannot reliably generate synchronized dialogue in-shot.
Use these alternatives:

| Dialogue Need | Solution |
|---|---|
| Single character speaking | Character Script to Video App (Lip Sync) |
| Two characters in conversation | Lip Sync with Multi-Face, 2 speakers |
| Character monologue with emotion | Act-Two (performance capture) |
| Voice-over narration (no lip sync) | Text to Speech node in Workflow |
| No dialogue — pure visual | Music + ambient SFX only |
| Foreign language version | Voice Dubbing node (29 languages) |

---

## RUNWAY WORKFLOW FOR SHORT FILM

```
PHASE 1 — CHARACTER REFERENCES
  [Character A reference image] via Gen-4 Image
  [Character B reference image] via Gen-4 Image
  [Location reference image] via Gen-4 Image

PHASE 2 — SCENE GENERATION (by scene group)
  Scene 1, Clip 1 → Gen-4.5 Turbo (first frame = location ref)
  Scene 1, Clip 2 → Gen-4.5 Turbo (first frame = Last Frame of Clip 1)
  Scene 1, Clip 3 → Gen-4.5 Turbo (first frame = Last Frame of Clip 2)
  [repeat for all scenes]

PHASE 3 — DIALOGUE (if any)
  [Character A script] → Character Script to Video App
  [Character B script] → Character Script to Video App

PHASE 4 — AUDIO
  [Narration script] → Text to Speech (ElevenLabs)
  [Score description] → Text to SFX
  [Ambient sound] → Text to SFX (multiple nodes, one per environment)

PHASE 5 — ASSEMBLY
  All clips → Stitch node (in scene order)
  Stitch output + narration + score + ambient → Add Audio
  → Upscale 4K
```

---

## NARRATIVE PROMPT DISCIPLINE

Unlike commercial prompts (one clear action), narrative prompts must
establish:
1. **Emotional state** of the character (not just physical action)
2. **Atmospheric details** that serve the story
3. **Camera position relative to the story** (observational vs. immersive)

**Example — Weak (commercial mindset):**
> "A man walks into a warehouse at night"

**Example — Strong (narrative mindset):**
> "Medium shot from inside the darkened warehouse — a silhouette fills the
> roll-up door entrance as it slides open, backlit by the amber sodium
> vapor lights of the parking lot outside. The man pauses in the threshold,
> scanning the space. Camera holds static and observational, as if watching
> from the shadows. Shot on Sony FX3, 35mm equivalent, deep shadow detail
> preserved, fine film grain, documentary realism."

---

## CREDIT ESTIMATES FOR NARRATIVE

| Length | Clips | Draft (Turbo) | Final (Full) | With 4K |
|---|---|---|---|---|
| 60s vignette | 10 | ~260 credits | ~620 credits | +120 |
| 90s short | 15 | ~390 credits | ~930 credits | +180 |
| 3min short film | 30 | ~780 credits | ~1,860 credits | +360 |

Always add 25% buffer for retakes on critical narrative moments.
Budget for 2 takes on any clip with character action or emotion.
