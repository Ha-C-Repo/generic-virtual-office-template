# TEMPLATE: 30-Second Commercial
## Pattern — do not copy content, reuse structure only

---

## STRUCTURE (6 clips × 5 seconds)

| Time | Beat | Purpose | Shot Type | Audio |
|---|---|---|---|---|
| 0:00-0:05 | HOOK | Stop the scroll / disrupt | Bold wide OR disorienting ECU | No VO — sound only or silence |
| 0:05-0:10 | PROBLEM | Name the pain or desire | Medium shot, intimate | VO line 1 — problem statement |
| 0:10-0:15 | AGITATE | Make the problem feel real | Close-up detail or reaction | VO line 2 — amplify tension |
| 0:15-0:22 | SOLUTION | Product/service in action | Medium or MCU — show the work | VO line 3 — solution stated |
| 0:22-0:27 | PROOF | Result or emotional payoff | Wide or aspirational shot | VO line 4 — outcome/benefit |
| 0:27-0:30 | CTA | Single clear action + brand | Logo card or CTA overlay | VO line 5 — call to action |

---

## SCRIPT FORMAT

```
[PROJECT NAME] — 30s Commercial
Total VO word count: 65-75 words max (130-150 WPM)

CLIP 01 (0:00-0:05) — HOOK
VISUAL: [description]
AUDIO: [music sting / silence / ambient sound — NO VO]

CLIP 02 (0:05-0:10) — PROBLEM
VISUAL: [description]
VO: "[problem statement — 10-12 words]"

CLIP 03 (0:10-0:15) — AGITATE
VISUAL: [description]
VO: "[tension amplifier — 10-12 words]"

CLIP 04 (0:15-0:22) — SOLUTION
VISUAL: [description]
VO: "[solution statement — 15-18 words]"

CLIP 05 (0:22-0:27) — PROOF
VISUAL: [description]
VO: "[outcome/benefit — 10-12 words]"

CLIP 06 (0:27-0:30) — CTA
VISUAL: [brand logo / website URL / CTA card]
VO: "[CTA — 5-8 words]"
ON-SCREEN: [URL] | [tagline]
```

---

## RUNWAY WORKFLOW PLAN (6 nodes)

```
Reference image → Gen-4 Image (lock visual style)

Text [Clip 01 prompt] → Gen-4.5 Turbo (first frame = reference)
Text [Clip 02 prompt] → Gen-4.5 Turbo (first frame = Last Frame of 01)
Text [Clip 03 prompt] → Gen-4.5 Turbo (first frame = Last Frame of 02)
Text [Clip 04 prompt] → Gen-4.5 Turbo (first frame = reference OR Last Frame of 03)
Text [Clip 05 prompt] → Gen-4.5 Turbo
Text [Clip 06 prompt] → Gen-4.5 Video (brand card — no character)

All 6 outputs → Stitch node (in order 01→06)
Text [VO script] → Text to Speech
Text [SFX/music] → Text to SFX
Stitch output + TTS + SFX → Add Audio
Add Audio output → Upscale 4K (if delivery requires it)
```

**Credit Estimate:**
- 6 clips × Gen-4.5 Turbo (25 each) = 150
- Reference image = 10
- TTS + SFX = 15
- 4K upscale (30s × 2cr/s) = 60
- **Draft total: ~235 credits**
- **Final quality (Gen-4.5 full): ~470 credits**

---

## DELIVERABLES CHECKLIST

- [ ] 16:9 master (30s, no captions)
- [ ] 16:9 master (30s, with captions)
- [ ] 9:16 vertical cut (30s, reframed)
- [ ] 1:1 square cut (30s, reframed)
- [ ] 15s cut-down (clips 01, 04, 05, 06)
- [ ] 6s bumper (clip 01 + clip 06)
