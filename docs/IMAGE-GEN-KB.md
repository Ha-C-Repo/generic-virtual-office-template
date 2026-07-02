# Free vs Paid AI Image Generators - Knowledge Base (Your Company scope)

Source: https://www.youtube.com/watch?v=c30mA4z5GyQ ("Forget Nano Banana? This Is FREE", host AI Samson / Samson Vowles, 31:22, published 2026-06-26)
Models tested: NVIDIA Cosmos 3, Ideogram 4 (free/open-weight) vs GPT Image 2, Nano Banana Pro (paid) plus 1 bonus (Reve 2)
Extracted: 2026-06-26

Scope note (firewall). This file is Your-Company-scoped: it holds the neutral tool reference (model facts, test results, verdict) plus the Your Company marketing-visual application only. Cross-business application findings for Pinnacle, DOVA, AIRS, and the all-business OpenMontage hierarchy were intentionally kept OUT of this Your Company file per the business firewall (0.ai-context/CLAUDE.md, never blend the businesses, do not move files between business folders). Those cross-business findings are held separately and routed by Joseph to each business's own location; they are not part of this file.

## Provenance and Confidence Note

Confidence: LOW. Everything below the model facts is one creator's subjective benchmark from a single 31-minute review video, not Your Company doctrine and not an independent test. The quality verdicts (who won each test) are that creator's opinion on his own prompts. Prices, parameter counts, hardware figures, and the open or free claims are as shown or said on screen, and several Cosmos 3 figures came from an on-screen AI-overview panel the host pulled up rather than NVIDIA primary-source pages (flagged inline below). Per verify-do-not-generate: treat every number and every license or commercial-use claim here as a lead to confirm against the vendor and the actual model license before any business adoption, not as fact. Anything that would touch a client or revenue deliverable must be license-verified by Joseph first (see Commercial Use Warnings).

Captions note. This video had YouTube auto-captions, so it was watched with a full transcript plus sampled 1024px frames across three timestamp-guided passes (the 17:31-21:28 Higgsfield sponsor segment was skipped). No Whisper transcription was needed here. Separately, no Whisper API key is currently configured on this machine (no GROQ_API_KEY or OPENAI_API_KEY in ~/.config/watch/.env), so any FUTURE video that lacks captions will run frames-only with no transcript until Joseph sets a key. Flagged in Recommended Actions.

## Model Profiles

### NVIDIA Cosmos 3  [FREE / OPEN-WEIGHT]
Access: web (Hugging Face Space, the demo shown is `multimodalart/Cosmos3-Super-Text2Image`, 64B with NVFP4 quantization, "Running on ZERO"), local download and run (GitHub repo plus model cards), and the underlying weights `nvidia/Cosmos3-Nano` and `nvidia/Cosmos3-Super` on Hugging Face.
Cost: open weights, free to download. On Hugging Face you spend "your own credits" for hosted generation. No per-image free-tier figure was stated for Cosmos itself.
Tech: NVIDIA "Cosmos Lab" omnimodal world model for Physical AI. Built to train robots and self-driving cars, it also generates images, video, and audio. Unified architecture combining an autoregressive reasoner and a diffusion generator with shared attention. The host pulled an AI-overview panel stating two sizes: Nano at about 16B (8B reasoner plus 8B generator) and Super at about 64 to 65B (32B plus 32B). [AI-summarized, confirm against NVIDIA.]
How to use (from 06:04-07:12): "Cosmos you can download and run on your own machine. However, you are going to need an insanely powerful computer." Cloud path: go to Hugging Face, search the cosmos model, choose nano or super, then enter a prompt and generate using your own credits. The demo used the Cosmos Super model.
Commercial use: not shown or stated in the video. UNSTATED. NVIDIA open-model licenses carry specific commercial terms, so this must be read before any business use.
Local-run feasible: yes, but hardware-heavy. The AI-overview panel said Nano targets workstation-grade hardware (example given: NVIDIA RTX PRO 6000) and Super requires datacenter compute (NVIDIA Hopper and Blackwell). [AI-summarized, confirm.] Practical path today is the Hugging Face cloud Space unless we own a high-VRAM NVIDIA workstation card.

### Ideogram 4  [FREE / OPEN-WEIGHT]
Access: web app (ideogram.ai) plus an API (API Dashboard and API Docs links present in the app). The host also said "you can download this one too, it is smaller," and the LMArena board labels it "Ideogram Open Model," so open weights exist. Note: the host's word was "open-weight"; some write-ups say "open-source." Treat it as an openly released model and verify the exact license.
Cost: Free plan $0 (free credits with Google, Apple, or Microsoft sign-in, "Limited public generation," API access, community gallery). Free tier gives 12 "slow credits" per day, resetting about every 17 hours. Plus plan $20 per month (private generation, 1,000 priority credits per month, unlimited slow credits, unlimited character consistency, quality export). Pro plan $60 per month per the narration.
Tech: built around "text and design." Strong typography and graphic-design focus, plus cinematic imagery, photography, logos, and posters. Editing primitives by name: Remove background, Prompt edit, Layerize text, Extend, Reframe. Supports Custom Models that bake a brand into the model weights so every output matches brand standards.
How to use (from 06:04-07:12): use the website (or download and install), sign in for free credits, select an aspect ratio, enter a prompt, and generate. Free users get 12 images per day.
Commercial use: no explicit license shown. The free plan lists "Limited public generation," which strongly implies free-tier images are publicly visible. Private generation is a paid (Plus and above) feature. UNSTATED license, and free-tier privacy is a business blocker (see Commercial Use Warnings).
Local-run feasible: claimed ("you can download it, install it on your own machine") and "smaller" than Cosmos, but no hardware, VRAM, or GPU requirement was shown. The demonstrated and recommended path is the web app or API.

### GPT Image 2  [PAID]
Access: web and API via OpenAI. Not demonstrated step by step; used as a paid comparison baseline.
Cost: on the Artificial Analysis board shown, "OpenAI GPT Image 2 (high)" was listed at about $211 per 1,000 images, the most expensive option on screen.
Tech: OpenAI's image model (referred to as "GPT Image 2" / "GPT images 2"). Topped both leaderboards shown (LMArena gpt-image-2 medium score 1385, rank 1; Artificial Analysis GPT Image 2 high 1340, rank 1).
How to use: not shown in this video.
Commercial use: standard paid OpenAI commercial terms (not detailed in the video; confirm current OpenAI usage terms).
Local-run feasible: no. Closed, API only.

### Nano Banana Pro  [PAID]
Access: web and API via Google (this is Google Gemini 3 Pro Image, "gemini-3-pro-image-preview"). Used as a paid comparison baseline, not demonstrated step by step.
Cost: on the Artificial Analysis board, "Google Nano Banana Pro (Gemini 3 Pro Image)" was listed at about $134 per 1,000 images.
Tech: Google Gemini 3 Pro Image. Strong on artistic-style and "cute" character rendering (won 3D animation and oil painting). Placed around rank 5 to 8 on LMArena (multiple Gemini variants shown).
How to use: not shown in this video.
Commercial use: standard paid Google terms (confirm current Gemini image terms).
Local-run feasible: no. Closed, API only.

### Reve 2  [BONUS - FREE TO TRY]
Access: web app at reve.com (host says "Revy 2," wordmark reads "Reve") with an API option (an API nav link is present). Login required (a "Sign in with Google" screen was shown).
Cost: free to try. Host: "Revy will let you try it out entirely for free... All you have to do is log in and go to start creating." A "Pricing" nav link exists but was not opened, so no dollar figure was shown. A "5d left" badge suggests a time-limited trial or contest.
Tech: separates planning from rendering, combining the steerability of autoregressive models with the aesthetics of diffusion. Standout feature is element-level control: it auto-segments a generated image into named, selectable layers (for example woman, motorcycle, road, sign, sea) each with its own prompt, so you can change one element without the whole-image drift that the host says plagues GPT Image and Nano Banana Pro edits. Tagline: "Images you can touch." Ranked rank 2 on the LMArena text-to-image board ("reve-2.0", score 1273), above several Gemini and GPT variants.
Commercial use: unstated (pricing and license not opened on screen).
Local-run feasible: no evidence of open weights. Web and API only.

## Test Results

Placements below are the host's on-screen Rank badges (1 best, 4 worst) per test, his subjective opinion. Free models are Cosmos 3 and Ideogram 4.

| Test | Cosmos 3 | Ideogram 4 | GPT Image 2 | Nano Banana Pro | Winner |
|------|----------|-----------|-------------|-----------------|--------|
| Blind Test (07:12) | unlabeled | unlabeled | unlabeled | unlabeled | No declared winner (point: free rivals paid) |
| Realism and Hands (08:30) | 4th | 1st | 2nd | 3rd | Ideogram 4 (FREE) |
| Human Portraits (10:22) | 4th | 2nd | 1st | 3rd | GPT Image 2 |
| Text Rendering (12:16) | 4th | 1st | 2nd | 3rd | Ideogram 4 (FREE) |
| Cinematic (14:49) | tied 3rd | 2nd | 1st | tied 3rd | GPT Image 2 |
| Anime (21:28) | 2nd | 4th | 1st | 3rd | GPT Image 2 |
| 3D Animation (22:45) | 4th | 3rd | 2nd | 1st | Nano Banana Pro |
| Oil Paintings (24:44) | 2nd | 3rd | 4th | 1st | Nano Banana Pro |

Win tally: GPT Image 2 won 3 (portraits, cinematic, anime), Ideogram 4 won 2 (realism/hands, text), Nano Banana Pro won 2 (3D, oil). Cosmos 3 won none but placed 2nd in anime and oil painting, ahead of paid models in both.

### Per-Test Notes

Blind Test (07:12). Four unlabeled jeweler-hands images, one per model, viewer invited to pick blind. No vote reveal. Host's point: "I do not think that it is possible to determine that the free models were inferior to the paid models in this example. And that is exactly the point."

Realism and Hands (08:30). Prompt: a jeweler's weathered hands inspecting a diamond ring with bands, a ring box, and a glass of water. No extra or missing fingers on any model. Ideogram 4 gave the most realistic, weathered hands and pleasant soft focus. GPT Image 2 chose a different over-the-shoulder composition. Cosmos 3 had correct anatomy but less detail and a small-looking ring and glass.

Human Portraits (10:22). Prompt demanded natural skin texture with visible pores and no beauty-filter look. GPT Image 2 had marginally the best skin texture. Ideogram 4 was more cinematic and moodier with strong emotion in the eyes. Nano Banana Pro had soft daylight and a slightly fuller face. Cosmos 3 was last but "not a million miles away."

Text Rendering (12:16). Prompt required four exact text targets: a sign "THE INKWELL", a chalkboard "New Arrivals Today", a window notice "Open 9 to 6, Closed Sundays", and a price "£12.99". GPT Image 2 spelled every element correctly including the pound sign and a bonus legible side sign, its only flaw a too-perfect chalkboard font. Ideogram 4 was ranked first for design and placement (correct "THE INKWELL" and clean chalk font) though the window notice was rendered very small. Nano Banana Pro misspelled "Closed" as "Clored" and absurdly duplicated the shop name in a window reflection. Cosmos 3 dropped "THE" (showing only "INKWELL"), scrambled the hours line into "Open 9 / Closed 6 / Sundays", and used "$" instead of "£". Key point: for guaranteed spelling accuracy GPT Image 2 was cleanest, while Ideogram 4 is the strongest free option and won the host's overall text ranking.

Cinematic (14:49). Prompt: a neon rain-soaked motorcyclist with a billboard "WELCOME TO THE FUTURE". GPT Image 2 took a dramatic toward-camera composition with strong motion blur. Ideogram 4 had "absolutely stunning" reflections but a too-symmetric, repetitive composition and odd rider scale. Cosmos 3 did its best work yet on mechanical realism and tarmac reflections but mangled the surrounding neon signage into gibberish. Nano Banana Pro went warm-toned against a cyan-neon brief.

Anime (21:28). GPT Image 2 was the most detailed and cinematic. Cosmos 3 was "exquisite, nothing subpar" and took a clear 2nd ahead of both paid Nano Banana Pro and Ideogram 4. Ideogram 4 was uncharacteristically weak with slightly mangled hands.

3D Animation (22:45), Pixar-style orange cat. Nano Banana Pro won on "sheer cuteness," tonal range, and depth. GPT Image 2 was almost over-detailed with too many individual hairs. Cosmos 3 was decent but looked flat. Ideogram 4 drifted to photorealistic rather than stylized.

Oil Paintings (24:44). Nano Banana Pro won with intentional composition and convincing impasto inside a picture frame. Cosmos 3 took 2nd with strong palette-knife clouds, ahead of paid GPT Image 2, which looked too digital and over-ordered.

## Final Verdict

The host gave a use-case-segmented verdict, not a single ranking. Did free beat paid? No, not overall. His exact lines: "if you are looking for the models that perform well across the board in various different situations, I do think that still GPT images 2 is the best all round model for any situation." Within niches the free models hold their own: "Idog 4 is exceptional for graphic design use cases and certainly is as good, if not better, at rendering out complex text situations," and "as for creating dynamic realistic scenes of mechanical objects, Cosmos 3 is specifically created for this use case and there it is on par with other leading models." The broader takeaway he repeats is that "these open image models are getting better and better" and in the blind test are no longer distinguishable as inferior to paid.

Bottom line (his opinion, low-confidence): GPT Image 2 (paid, OpenAI) is the overall winner and best all-rounder. Nano Banana Pro (paid, Google) wins artistic-style work (3D, oil). The two free open-weight models rival but do not beat the paid leaders overall, and each wins a specific niche: Ideogram 4 for text and graphic design, Cosmos 3 for dynamic, mechanical, and physically realistic scenes.

## Your Company Application - Marketing Visuals Only

This applies to Your Company marketing and capability visuals only (capability stills, social posts, marketing graphics, brochure imagery). It does NOT touch client bid renderings, which stay locked to the real S0.0 3D rendering doctrine; no AI image model goes near a bid render or implies member accuracy.

For Your Company marketing stills, Ideogram 4 is the best free first-try because this work usually carries text (capability one-pagers, social cards, headlines) and Ideogram won the host's text and realism tests. Use GPT Image 2 as the paid backstop when exact spelling on a high-visibility asset must be guaranteed, since even paid Nano Banana Pro misspelled "Closed" as "Clored" in the text test. Cosmos 3 (free, via the Hugging Face Space) is the candidate for marketing imagery of steel, machinery, and physically grounded industrial scenes, the Style 01 industrial-cinematic lane, where the host rated it on par with the leaders, subject to the license and hardware caveats below.

Where this slots in. Your Company motion and advertising image-gen lives in the Video Creation/ studio (the Your Company studio, Style 01). Any additive image-gen provider entry for Your Company belongs there, in Video Creation/, confirmed against Video Creation/FOLDER_INSTRUCTIONS.md and Video Creation/CLAUDE.md before writing, never in another business's hierarchy. This file does not edit any provider hierarchy; it only records candidates. Adoption is gated on the license verification and the privacy and hardware caveats below.

## Local Build Doctrine Assessment

Ranked by doctrine fit (free, open-weight, locally runnable, quality-competitive, additive):

1. Cosmos 3 is the strongest doctrine fit on paper because it is genuinely open-weight with published model cards, a GitHub repo, and downloadable Nano and Super weights, and it is quality-competitive in its lane (mechanical and physical realism, 2nd in anime and oil). The blocker is hardware: per the AI-overview figures (unverified), Nano targets an RTX PRO 6000-class workstation GPU and Super needs datacenter Hopper or Blackwell. On a standard Windows dev workstation we likely cannot self-host Super, and Nano is borderline depending on the actual card. Until hardware is confirmed, run Cosmos 3 through the free Hugging Face Space rather than truly local.
2. Ideogram 4 is open-weight and "smaller," so it is the more plausible candidate for actual self-hosting, but the video showed no hardware figures and demonstrated only the web app and API. Today the realistic free path is the web or API free tier (12 images per day), not local.
3. Reve 2 is free to try but shows no sign of open weights, so it is web and API only and a weaker doctrine fit despite being free.

Can either free model reduce a current paid dependency for Your Company marketing visuals? Partially. Ideogram 4 free can take a meaningful share of text-and-design and general still generation as a free-first try, subject to the 12-per-day cap and license. Cosmos 3 (cloud) can take industrial and mechanical scenes. Neither fully replaces GPT Image 2 for best all-round quality, so the right posture is free-first-try with a paid escalation. Hardware to self-host: Cosmos Nano needs a high-VRAM professional NVIDIA GPU (RTX PRO 6000 class, unverified); Cosmos Super needs datacenter GPUs; Ideogram hardware is unstated.

## Commercial Use Warnings

Neither free model's license was shown in the video, so neither is cleared for Your Company client or revenue deliverables yet. Two specific blockers to resolve before adoption:

1. License terms are unverified for both Cosmos 3 and Ideogram 4. NVIDIA open-model licenses and the Ideogram Open Model license each carry their own commercial-use conditions. Do not ship Cosmos 3 or Ideogram 4 output on any Your Company client-facing or revenue deliverable until Joseph reads and confirms the actual license permits commercial use. This must be confirmed against the real model licenses, not inferred from the video.
2. Ideogram free-tier privacy. The free plan lists "Limited public generation," which means free-tier images are likely public. Private generation is a paid feature (Plus at $20 per month and up). For any confidential, pre-launch, or client work, the free tier is unsuitable; use the paid Plus plan for private generation. Reve 2 pricing and license were not opened on screen and are also unverified.
GPT Image 2 and Nano Banana Pro are standard paid services with their providers' commercial terms; confirm current OpenAI and Google image-usage terms, but they carry no open-license ambiguity.

## Recommended Actions (Your Company)

1. Test Ideogram 4 first for Your Company marketing stills (text-heavy capability and social graphics). Action for Joseph: create an account, generate an API key, and confirm the Ideogram Open Model license permits commercial use before any Your Company deliverable. Budget the $20 per month Plus plan for private generation if the free public-generation limit is a problem.
2. Try Cosmos 3 on the Hugging Face Space for industrial and mechanical marketing imagery (Style 01). Action for Joseph: confirm whether our workstation GPU can run Cosmos Nano locally (needs a high-VRAM professional NVIDIA card, figure unverified) and read the NVIDIA Cosmos license for commercial terms. Until then, cloud only.
3. Any additive image-gen provider entry for Your Company goes in the Video Creation/ studio, confirmed against its FOLDER_INSTRUCTIONS.md and CLAUDE.md, keeping GPT Image 2 as the paid escalation. Do not change the locked Your Company bid-render doctrine.
4. Whisper key. No GROQ_API_KEY or OPENAI_API_KEY is set in ~/.config/watch/.env, so future caption-less videos run frames-only. Action for Joseph: add a Groq key (preferred, cheaper and faster) or an OpenAI key to unlock Whisper transcription.

Joseph action gating before adoption: license verification on Cosmos 3 and Ideogram 4, the Ideogram private-generation decision, the GPU capability check for local Cosmos, and a Whisper key for caption-less videos.
