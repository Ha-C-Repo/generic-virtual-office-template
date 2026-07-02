---
name: style-01-corporate-cinematic
description: Generates corporate-cinematic brand video prompts for B2B, legal, finance, professional services, and industrial clients. Outputs Gen-4.5 Text+Image to Video prompts that satisfy all 16 Anti-AI Laws, append the Style 01 token verbatim, and conform to operator-to-operator voice. Use for any corporate-cinematic Your Company deliverable or external commercial work in adjacent verticals.
---

# Skill: style-01-corporate-cinematic

## When to invoke

User says any of:
- "Write Style 01 prompts for this shot list"
- "Generate corporate cinematic prompts"
- "Corporate cinematic, dark steel and warm amber"
- "B2B brand video, finance, legal, or industrial"

## Inputs

Required:
- Shot list with N clips. Either a path to a shot list MD file or pasted rows describing each clip (shot type, subject, action, environment).

Optional:
- Aspect ratio (default 16:9 horizontal for YouTube and website hero).
- Brand override (default corporate-cinematic generic, can be specified per client).

## Style 01 token (appended verbatim as the final sentence of every prompt)

```
shot on ARRI Alexa Mini LF, 32mm Cooke S4 lens, T2.0, warm tungsten practical window light from the left, cinematic color grade with deep shadows and controlled highlights, fine ARRI sensor grain
```

## Style 01 visual vocabulary

Always present in the prompt body:
- **Color palette:** dark steel #1F2A44 / #2D3142, warm amber #D97706, oxidized iron #4A3C2A, raw plate steel highlights, polished walnut interiors.
- **Materials:** brushed steel, weathered oak desk, glass-walled conference room, leather portfolio, ink and paper, drafting tools, charcoal wool suit fabric, machined aluminum, mill-finished surfaces (gloves and any close-frame hand work cropped above the wrist per Law 7).
- **Environments:** boardroom or executive office at golden hour, professional services interior under warm overhead light, working desk with a single tungsten lamp, Houston office tower interior at dusk, industrial interior with low-angle natural light.
- **Lighting:** warm tungsten practical light through a window, bay door, or overhead pendant from camera left. Deep shadow side opposite.
- **Camera:** 32mm Cooke S4 on ARRI Alexa Mini LF, T2.0, restrained movement (slow dolly, push-in, arc, lock-off), 5 seconds per clip.

## 16 Anti-AI Laws enforcement

Every prompt this skill produces must satisfy:

i.    Image-to-video for any human subject (use existing NBP reference)
ii.   One light source: "warm tungsten practical light from camera left"
iii.  Style 01 token as the final sentence (literal text above)
iv.   Camera body and lens: "ARRI Alexa Mini LF, 32mm Cooke S4"
v.    Film grain: "fine ARRI sensor grain" (part of style token)
vi.   Medium close-up or tighter; no wide interiors with many small figures
vii.  No hands described close to frame; cuff or glove cropped above the wrist
viii. Motivated camera: name start, end, speed, and duration
ix.   Max 5 seconds per clip (1-second safety under the Law 9 ceiling)
x.    One action per clip; no scene transitions inside a single prompt
xi.   No AI cliches: no aerial drone of a downtown skyline, no generic handshake, no person-pointing-at-document hero shot, no laptop hero shot, no smiling-team group photo
xii.  Physics described: warm light pool wraps around surfaces, dust motes catch the beam, paper edges curl in still air, ambient room tone implied by visible material weight
xiii. No readable text or documents in frame; pages face-down or defocused, no signage rendered, no nameplates legible
xiv.  No silhouetted or middle-distance human figures; zero people preferred, or medium close-up max with face cropped
xv.   All stats, lower-thirds, wordmarks, URLs, phone numbers composited in post; never asked of Runway
xvi.  No symbols: spell out percentages, dollars, degrees, etc.

## Voice rules for VO and on-screen text (applied to script copy, NOT to Runway prompts)

These rules apply to the VO and on-screen text that lives alongside the clips, not to the Runway prompts themselves:

- **Tone:** precise, capable, unpretentious, operator-to-operator.
- **No consultant language.** No "we partner with," "trusted advisor," "synergize," "leverage," "best-in-class," "industry-leading."
- **No marketing fluff.** No "passion for quality," "people you can trust," "your vision, our craftsmanship."
- **Specific numbers over claims.** "Nine years operating in Houston" beats "decades of experience." Sourced specifics beat slogans.
- **Houston-grounded** when the client is Houston-based.
- **Owner signs the voice.** No anonymous corporate voice.


## Prompt formula

```
[SHOT TYPE] of [SPECIFIC SUBJECT WITH DETAILS] [ONE ACTION WITH PHYSICS],
[SPECIFIC ENVIRONMENT], [SINGLE LIGHT SOURCE + DIRECTION], [MOTIVATED CAMERA
MOVEMENT, start, end, speed, duration], [STYLE 01 TOKEN verbatim].
```

## Example output (corporate office hero, Clip 01 of a 30s commercial)

```
Tabletop medium close-up, slow push-in on a brushed-steel mechanical pencil
and a closed leather portfolio resting on a polished walnut conference table,
the portfolio shows soft directional highlights along the spine and a single
brass corner cap catches a tungsten reflection, a thin paper notebook edge
sits at frame edge with the pages face-down so no text is visible, a single
overhead pendant light spills warm tungsten through a tall office window from
camera left casting a long shadow across the table, no people visible, no
readable text anywhere in frame, no signage in focus, the camera performs a
slow eight-inch push-in from medium shot to medium close-up at constant speed
over five seconds, physics: warm light pool wraps the brass corner and rolls
across the wood grain, dust motes drift through the warm light shaft, the
portfolio leather catches a single soft highlight as the camera moves, shot
on ARRI Alexa Mini LF, 32mm Cooke S4 lens, T2.0, warm tungsten practical
window light from the left, cinematic color grade with deep shadows and
controlled highlights, fine ARRI sensor grain.
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
- `/runway-image-auto` consumes the reference prompt
- `/runway-video-auto` consumes each clip prompt
- `/runway-full-pipeline` orchestrates the full build using prompts from this skill
- `/runway-persistent-driver` drives the build to comple