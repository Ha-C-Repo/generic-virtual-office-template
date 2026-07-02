---
name: style-02-luxury-premium
description: Generates luxury and premium brand video prompts. Outputs Gen-4.5 Text+Image to Video prompts that satisfy all 16 Anti-AI Laws, append the Style 02 token verbatim, and conform to voice rules (no em-dashes, no banned vocabulary, no invented stats). Use for any luxury or premium brand video work.
---

# Skill: style-02-luxury-premium

## When to invoke

User says any of:
- "Write luxury / premium clip prompts"
- "Generate Style 02 prompts for this shot list"
- "Luxury aesthetic, navy and gold"
- "Premium brand video"

## Inputs

Required:
- Shot list with N clips. Either a path to a shot list MD file or pasted
  rows describing each clip (shot type, subject, action, environment).

Optional:
- Aspect ratio (default 9:16 vertical for LinkedIn / Reels).
- Brand override (default luxury / premium client).

## Style 02 token (appended verbatim as the final sentence of every prompt)

```
shot on ARRI Alexa Mini LF, 50mm Master Prime, warm tungsten key light left side, deep navy ambient fill, premium cinematic grade with soft gold accent highlights, fine 35mm grain structure
```

## Style 02 visual vocabulary

Always present in the prompt body:
- **Color palette:** deep navy #0a1f3d, warm cream #f7f5f0, soft gold #c9a961,
  dark walnut #2a1d12.
- **Materials:** walnut desk, leather portfolio, brass desk lamp, fountain pen
  on heavy cream paper, navy bound document, brass paperweight, glass tower
  with gold reflections, brass clock bezel.
- **Lighting:** warm tungsten from camera left, deep navy ambient fill on
  the right.
- **Camera:** 50mm Master Prime on ARRI Alexa Mini LF, T2.0, restrained
  movement (push-in, arc, orbit, dolly), 5 seconds per clip.

## 16 Anti-AI Laws enforcement

Every prompt this skill produces must satisfy:

i.    Image-to-video for any human subject (use existing NBP reference)
ii.   One light source: "warm tungsten key light from camera left"
iii.  Style 02 token as the final sentence (literal text above)
iv.   Camera body and lens: "ARRI Alexa Mini LF, 50mm Master Prime"
v.    Film grain: "fine 35mm grain structure" (part of style token)
vi.   Medium close-up or tighter; no wide shots with small figures
vii.  No hands described close to frame; sleeve cropped above the wrist max
viii. Motivated camera: name start, end, speed and duration
ix.   Max 5 seconds per clip (1-second safety under the Law 9 ceiling)
x.    One action per clip; no scene transitions inside a single prompt
xi.   No AI cliches: no glass-tower interiors, no handshakes, no laptop
      hero shots, no aerial drone, no whiteboard, no business-meeting tableau
xii.  Physics described: reflections slide, paper edges curl, brass micro-
      reflection shifts, heat-haze distortion
xiii. No readable text or documents in frame; pages face-down or defocused,
      clock dials defocused, no logos rendered
xiv.  No silhouetted or middle-distance human figures; zero people preferred,
      or medium close-up max with face cropped
xv.   All stats, lower-thirds, wordmarks, URLs, phone numbers composited in
      post; never asked of Runway
xvi.  No symbols: spell out percentages, cents, dollars, etc.

## Voice firewalls (Mode B applied to prompt copy)

- **No em-dashes anywhere.** Use periods, commas, semicolons, parentheses.
- **No banned vocabulary:** "leverage," "synergy," "unlock," "empower,"
  "deep dive," "low hanging fruit," "circle back," "drive value,"
  "actionable insights," "operationalize," "ideate," "robust," "holistic,"
  "end-to-end," "game-changing," "It's not just X, it's Y," etc.
- **No invented stats or claims.** Every on-screen number, credential, or stat must be sourced and approved. Flag uncertainty rather than fabricating.

## Prompt formula

```
[SHOT TYPE] of [SPECIFIC SUBJECT WITH DETAILS] [ONE ACTION WITH PHYSICS],
[SPECIFIC ENVIRONMENT], [SINGLE LIGHT SOURCE + DIRECTION], [MOTIVATED CAMERA
MOVEMENT — start, end, speed, duration], [STYLE 02 TOKEN verbatim].
```

## Example output (30s LinkedIn Clip 01)

```
Tabletop medium close-up, slow six-inch push-in on a dark walnut executive
desk, a closed brown leather portfolio sits centered on the surface with a
black lacquer fountain pen resting on top, a brass desk lamp is heavily out
of focus in the deep background casting a warm tungsten pool of light from
camera left, the leather grain and pen barrel catch the light revealing fine
surface detail, no people, no faces, no hands, no readable text anywhere in
frame, no documents in focus, the camera performs a slow six-inch push-in
from medium shot to medium-close-up at constant speed over five seconds,
physics: the pen barrel reflection slides as the camera moves and the warm
light pool deepens at the closer focal point, shot on ARRI Alexa Mini LF,
50mm Master Prime, warm tungsten key light left side, deep navy ambient
fill, premium cinematic grade with soft gold accent highlights, fine 35mm
grain structure.
```

## Output format

For each clip in the shot list, the skill returns:

```
### Clip <N>: <one-line shot description>
```
<full prompt as above, ready to paste into a Runway Text node>
```

Plus, at the top of the output:

```
### Reference A (or B, or C as needed)
```
<full image prompt for the reference image upstream of these clips>
```
```

## Related skills
- `/runway-image-auto` — consumes the reference prompt
- `/runway-video-auto` — consumes each clip prompt
- `/runway-full-pipeline` — orchestrates the full bui