# TEMPLATE: 15-Second Pre-Roll Ad
## Pattern — do not copy content, reuse structure only

---

## CRITICAL RULES FOR PRE-ROLL

1. **Must survive the skip button at 5 seconds** — the hook must work on
   its own even if the viewer bails after clip 1.
2. **Must work with sound OFF** — the first 3 clips should be visually
   self-explanatory without audio.
3. **Single message only** — one idea, one CTA. No subplots.
4. **No brand logo in first 2 seconds** — lead with the hook, not the brand.

---

## STRUCTURE (3 clips × 5 seconds)

| Time | Beat | Purpose | Shot Type | Audio |
|---|---|---|---|---|
| 0:00-0:05 | HOOK | Visual arrest — no logo, no intro | Bold ECU or unexpected angle | Music sting / silence only |
| 0:05-0:10 | VALUE | What they get — one clear benefit | Medium shot — product or result | VO line 1 + 2 (full value prop) |
| 0:10-0:15 | CTA | Brand + single instruction | Clean CTA card or MCU + URL | VO line 3 (CTA) + logo |

---

## SCRIPT FORMAT

```
[PROJECT NAME] — 15s Pre-Roll
Total VO word count: 32-37 words max

CLIP 01 (0:00-0:05) — HOOK
VISUAL: [unexpected, arresting — do NOT open with logo or brand name]
AUDIO: [music sting or dramatic silence — NO VO]

CLIP 02 (0:05-0:10) — VALUE
VISUAL: [product in use or result demonstrated]
VO: "[value proposition — 20-22 words]"

CLIP 03 (0:10-0:15) — CTA
VISUAL: [clean atmospheric plate matching brand palette; no readable text in frame — wordmark / URL / tagline composited in POST per Anti-AI Law 15]
VO: "[CTA — 10-12 words]"
POST COMPOSITE: [canonical logo] | [URL in brand typography] | [Tagline if applicable] — overlay in NLE, never ask Runway to render
```

---

## HOOK FORMULAS FOR PRE-ROLL

The hook must stop a viewer mid-scroll in under 1 second visually.

- **The Contrast:** Open on something unexpected that contradicts the brand
  (e.g., for a law firm — extreme close-up of a ticking clock, no context)
- **The Process:** Start in the middle of something visually compelling
  (e.g., for a product — macro shot of it being assembled or poured)
- **The Result:** Show the outcome before explaining how to get it
  (e.g., for a consulting firm — a signed deal on a table, champagne,
  people standing — then explain what got them there)
- **The Question:** Black screen with white text for 2 seconds, then visual
  (e.g., "What if your biggest competitor knew your bid price?" — cut to action)

---

## RUNWAY WORKFLOW PLAN (3 nodes)

```
Reference image → Gen-4 Image (lock visual style)

Text [Clip 01 prompt] → Gen-4.5 Turbo (first frame = reference OR style-only)
Text [Clip 02 prompt] → Gen-4.5 Turbo (first frame = reference image)
Text [Clip 03 prompt] → Gen-4.5 Video (brand card — static or subtle motion)

All 3 outputs → Stitch node (in order 01→03)
Text [VO — 32-37 words] → Text to Speech (ElevenLabs)
Text [SFX/music underscore] → Text to SFX
Stitch output + TTS + SFX → Add Audio
```

**Credit Estimate:**
- 3 clips × Gen-4.5 Turbo (25 each) = 75
- Reference image = 10
- TTS + SFX = 10
- **Draft total: ~95 credits**
- **Final quality (Gen-4.5 full): ~215 credits**

---

## PLATFORM NOTES

- **YouTube:** 16:9 only. Must not have overlay text in bottom 10% (YouTube controls).
- **LinkedIn pre-roll:** 16:9. Captions required — most watched muted.
- **Facebook/Instagram in-stream:** 16:9 or 4:5. Vertical performs better on mobile.

---

## DELIVERABLES CHECKLIST

- [ ] 16:9 master (15s, no captions)
- [ ] 16:9 master (15s, with captions)
- [ ] 9:16 vertical cut (reframed for Instagram/TikTok)
- [ ] 6s bumper cut (clips 01 + 03 only, 3s each)
