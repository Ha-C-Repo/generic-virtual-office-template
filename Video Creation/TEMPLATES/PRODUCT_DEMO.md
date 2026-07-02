# TEMPLATE: Product Demo Video
## Pattern — do not copy content, reuse structure only

---

## WHAT A PRODUCT DEMO DOES

A demo answers one question: "Does this do what it claims?"
It is not a commercial (emotion-first) or a brand film (belief-first).
It is evidence. Every clip must show something real about the product.

**The test:** Could the viewer describe exactly what the product does
after watching? If yes, the demo worked.

---

## DEMO TYPES — CHOOSE ONE

| Type | When to Use | Structure |
|---|---|---|
| **Hero / Lifestyle** | Launch, brand awareness | Product in aspirational context — beauty shots |
| **Feature Walkthrough** | E-commerce, SaaS, tech product | Each clip = one specific feature or capability |
| **Before / After** | Service, transformation, solution | Problem state → solution state → result state |
| **Process / How It Works** | Complex products, B2B | Step-by-step with VO narration |
| **Comparison** | Competitive market | Side-by-side or sequential contrast |

---

## STRUCTURE — 30-SECOND PRODUCT DEMO (5-6 clips × 5s)

| Time | Beat | Purpose | Shot Type | Audio |
|---|---|---|---|---|
| 0:00-0:05 | HERO SHOT | Product in beauty — aspirational context | ECU or close beauty shot | Music intro, no VO |
| 0:05-0:12 | FEATURE 1 | First key capability — shown, not described | Detail shot in use | VO: feature benefit in 1 sentence |
| 0:12-0:18 | FEATURE 2 | Second key capability | Close-up of interaction | VO: feature benefit in 1 sentence |
| 0:18-0:24 | LIFESTYLE | Product in real-world context | Medium lifestyle shot | VO: aspirational outcome |
| 0:24-0:28 | SOCIAL PROOF | Result, rating, or proof element | Text card or product + result | VO: proof statement |
| 0:28-0:30 | CTA | Where to buy or learn more | Clean product + URL | VO: CTA |

---

## STRUCTURE — 60-SECOND FEATURE WALKTHROUGH (10-11 clips × 5-6s)

| Time | Beat | Clip Count |
|---|---|---|
| 0:00-0:06 | Hero beauty shot | 1 |
| 0:06-0:16 | Problem context (why this product exists) | 2 |
| 0:16-0:30 | Feature 1 demo — shown in detail | 2-3 |
| 0:30-0:42 | Feature 2 demo — shown in detail | 2-3 |
| 0:42-0:52 | Lifestyle use (product in environment) | 2 |
| 0:52-1:00 | Social proof + CTA | 1-2 |

---

## SCRIPT FORMAT

```
[PROJECT NAME] — [30s/60s] Product Demo
Product: [name + one-line description]
Key differentiator: [what makes this product distinct]

CLIP 01 (0:00-0:05) — HERO SHOT
VISUAL: [beauty shot of product — ECU texture, macro detail, or elegant lifestyle setup]
AUDIO: [music sting, no VO — let the product speak visually]

CLIP 02 (0:05-0:12) — FEATURE 1
VISUAL: [product being used — show the feature, not a person using it]
VO: "[Feature benefit — 10-12 words. State what it DOES, not what it IS.]"

CLIP 03 (0:12-0:18) — FEATURE 2
VISUAL: [detail of second feature or capability]
VO: "[Feature benefit — 10-12 words.]"

CLIP 04 (0:18-0:24) — LIFESTYLE
VISUAL: [product in its natural context — kitchen, desk, construction site, etc.]
VO: "[Outcome for user — 10-12 words.]"

CLIP 05 (0:24-0:28) — PROOF
VISUAL: [result, rating badge, testimonial text card, or product + satisfied user MCU]
VO: "[Proof statement — 8-10 words.]"

CLIP 06 (0:28-0:30) — CTA
VISUAL: [clean product shot OR URL + logo card]
VO: "[CTA — 6-8 words.]"
ON-SCREEN: [URL] | [Price or offer if applicable]
```

---

## PRODUCT PROMPT RULES

Product clips have different prompt priorities than character clips:

**Priority 1 — Product accuracy:** The product must look exactly right.
Always use the product image as first frame in Gen-4.5 Turbo.
Never use Text-to-Video for product clips — always Image-to-Video.

**Priority 2 — Surface texture:** Close-up product shots need texture detail.
Include: "macro lens detail, [material] texture clearly visible,
fine surface grain and imperfections preserved in high detail"

**Priority 3 — Interaction:** If a hand or person interacts with the product,
use medium shot or wider — never ECU of the interaction itself (hand artifacts).

**Priority 4 — Environment:** Keep backgrounds simple and consistent.
One background style per demo. Switching from studio white to lifestyle
setting mid-video breaks the visual language.

---

## RUNWAY WORKFLOW PLAN — 30s PRODUCT DEMO

```
PHASE 1 — PRODUCT REFERENCE IMAGE
  Upload product photography → use as first frame input for ALL product clips
  OR generate product hero → Gen-4 Image (studio seamless, Product Style 05)

PHASE 2 — VIDEO GENERATION
  Text [Clip 01: hero beauty] → Gen-4.5 Turbo (first frame = product ref)
  Text [Clip 02: feature 1 detail] → Gen-4.5 Turbo (first frame = product ref)
  Text [Clip 03: feature 2 detail] → Gen-4.5 Turbo (first frame = product ref)
  Text [Clip 04: lifestyle context] → Gen-4.5 Turbo (first frame = lifestyle ref)
  Text [Clip 05: proof element] → Gen-4.5 Video (text card or static)
  Text [Clip 06: CTA card] → Gen-4.5 Video (static brand card, minimal motion)

  OR use Product Shot Video Builder App for clips 01-04, then stitch with 05-06.

PHASE 3 — AUDIO
  Text [VO — 40-50 words for 30s] → Text to Speech
  Text [music: "clean upbeat product underscore, modern, not distracting"] → Text to SFX

PHASE 4 — ASSEMBLY
  Clips 01-06 → Stitch
  Stitch + TTS + SFX → Add Audio
  → Upscale 4K (for e-commerce or broadcast)
```

**Credit Estimate (30s):**
- 6 clips × Turbo (25) = 150
- Product reference image = 10
- Audio = 15
- 4K upscale = 60
- **Draft total: ~235 credits**
- **Final (full Gen-4.5): ~470 credits**

---

## DELIVERABLES CHECKLIST

- [ ] 16:9 master (30s or 60s, no captions)
- [ ] 16:9 with captions
- [ ] 1:1 square cut (Instagram/TikTok product tag format)
- [ ] 9:16 vertical cut (Reels/Shorts — reframe to product-forward)
- [ ] 4:5 cut (Instagram feed optimized)
- [ ] Still frames from product hero clips (for thumbnails / e-commerce PDP)
