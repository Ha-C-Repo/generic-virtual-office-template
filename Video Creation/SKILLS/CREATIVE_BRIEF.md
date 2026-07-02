---
name: Video Creative Brief Template
description: >
  Fillable creative brief template for any video production project.
  Claude uses this to intake client requests, define production scope,
  and establish creative direction before any generation begins. Output
  this filled template as confirmation before moving to script/shot list.
  Works alongside VIDEO_STUDIO.md and ANTI_AI.md.
version: "1.0"
updated: "2026-05"
---

# VIDEO CREATIVE BRIEF

> **READ THIS FIRST.** `CLAUDE.md` at the project root is the authoritative
> source for the current pipeline. This brief template predates the
> `script.json` storyboard (pipeline Step 2.5) and the HYBRID mode workflow.
> When filling out a brief in 2026-05 or later, also generate a `script.json`
> per `TEMPLATES/script.template.json` immediately after the brief is
> approved — Runway prompts and HyperFrames composition both pull from
> that single source of truth.

## Your Company Video Studio

---

## PROJECT OVERVIEW

**Project Name:** _______________________________________________

**Client / Brand:** ____________________________________________

**Industry:** _________________________________________________

**Date:** ___________________  **Deadline:** ___________________

**Brief Author:** Claude — AI Creative Director

---

## OBJECTIVE

**Video Type:**
- [ ] 30-second TV/Social Commercial
- [ ] 15-second Pre-Roll Ad (YouTube)
- [ ] Vertical Ad / Reel (TikTok, Reels, Shorts)
- [ ] 60-second Brand Film
- [ ] Product Demo Video
- [ ] Explainer Video
- [ ] Testimonial / Social Proof
- [ ] Event / Hype Video
- [ ] LinkedIn Content Video
- [ ] Website Hero Video
- [ ] Other: ________________________

**Primary Goal (select one):**
- [ ] Brand Awareness — people learn who we are
- [ ] Lead Generation — people inquire or sign up
- [ ] Sales / Conversion — people buy or hire
- [ ] Customer Education — people understand the product
- [ ] Employee / Internal Communication
- [ ] Social Engagement — shares, comments, follows

**North Star KPI:**
_________________________________________________________________
(Example: 3% click-through rate on LinkedIn / 500 website visits in 7 days)

---

## AUDIENCE

**Primary Target Audience:**
_________________________________________________________________

**Demographics:**
- Age range: _______________
- Industry/Profession: _______________
- Income/Company size: _______________
- Geographic focus: _______________

**Psychographic Profile (the emotional truth):**

Their core PROBLEM or DESIRE:
_________________________________________________________________

What they currently BELIEVE (that we need to change):
_________________________________________________________________

What we want them to FEEL after watching:
_________________________________________________________________

---

## MESSAGE

**Core Message (one sentence — what they must remember):**
_________________________________________________________________

**Supporting Points (2-3 maximum):**
1. _______________________________________________________________
2. _______________________________________________________________
3. _______________________________________________________________

**Tone (circle 3-5 adjectives):**

Authoritative / Warm / Urgent / Calm / Confident / Playful / Premium /
Trustworthy / Bold / Elegant / Raw / Aspirational / Honest / Direct /
Technical / Simple / Inspiring / Grounded / Sophisticated / Human

**Single Call-to-Action:**
_________________________________________________________________
(Example: "Visit yourcompany.example.com" / "Schedule a call" / "Learn more")

---

## PRODUCTION SPECS

**Duration:** ___________

**Primary Platform:** ___________________________________________

**Aspect Ratio:**
- [ ] 16:9 Landscape (YouTube, TV, Website)
- [ ] 9:16 Vertical (TikTok, Reels, Stories)
- [ ] 1:1 Square (Instagram Feed, Twitter)
- [ ] 4:5 Portrait (Instagram/LinkedIn Feed)
- [ ] 4:3 (Broadcast)

**Secondary Platforms (for cut-downs):**
_________________________________________________________________

**Deliverables Required:**
- [ ] Hero cut: ________ duration + ________ aspect ratio
- [ ] 15s cut-down
- [ ] 6s bumper
- [ ] 9:16 vertical version
- [ ] 1:1 square version
- [ ] Captioned version
- [ ] Clean version (no captions)

---

## VISUAL DIRECTION

**Visual Style System (from ANTI_AI.md):**
- [ ] Style 01 — Corporate Cinematic (dark navy, warm amber, premium)
- [ ] Style 02 — Luxury / Premium Consumer (minimal, editorial)
- [ ] Style 03 — Authentic / Documentary (natural, handheld, warm)
- [ ] Style 04 — Bold / Energetic (high contrast, kinetic, vivid)
- [ ] Style 05 — Minimal Product (studio seamless, clean)
- [ ] Custom (describe below)

**Custom Visual Direction:**
_________________________________________________________________
_________________________________________________________________

**Color Palette:**
Primary colors: ________________________________________________
Avoid these colors: ____________________________________________

**Lighting Direction:**
_________________________________________________________________
(Example: "warm afternoon window light, left side" or "cool morning overcast")

**Reference Videos or Moodboard:**
_________________________________________________________________
(URLs or description of comparable videos the client admires)

---

## MUST INCLUDE

Required on-screen elements:
- Logo placement: _______________________________________________
- Tagline/Slogan: _______________________________________________
- Website URL: _________________________________________________
- Phone/Email: _________________________________________________
- Other required copy: _________________________________________

Required visual elements:
- [ ] Brand colors on screen
- [ ] Company logo
- [ ] Product/service shown in use
- [ ] Real location (describe): _________________________________
- [ ] Other: ___________________________________________________

---

## MUST AVOID

Creative restrictions:
_________________________________________________________________
_________________________________________________________________
(Examples: no competitor names, no political imagery, no showing faces of
minors, avoid certain color associations, specific words not to use)

Content restrictions:
_________________________________________________________________

---

## ASSETS PROVIDED

**Brand Assets Available:**
- [ ] Logo file (format): _______________________________________
- [ ] Brand color codes: ________________________________________
- [ ] Brand font: _______________________________________________
- [ ] Existing footage/B-roll: __________________________________
- [ ] Photography: _____________________________________________
- [ ] Product images: __________________________________________
- [ ] Music or audio: __________________________________________

**Brand Guidelines Document:** Yes / No / Pending

---

## PRODUCTION APPROACH

**AI Generation Strategy:**
- All AI-generated via Runway (no real camera shoot)
- Hybrid: AI generation + provided brand assets overlaid
- AI-generated video + real product photography composited

**Character Approach:**
- [ ] No human characters (product/environment only)
- [ ] AI-generated characters (no specific person)
- [ ] Character Script to Video (scripted character delivery)
- [ ] Kling Motion Control (animate provided image with motion)
- [ ] Other: ___________________________________________________

**Voiceover Approach:**
- [ ] TTS Voiceover (ElevenLabs via Runway TTS node)
- [ ] Custom voice provided (upload to Runway)
- [ ] No voiceover (music only)
- [ ] Text on screen only (no audio VO)

**Music Approach:**
- [ ] AI-generated SFX underscore (Text to SFX node)
- [ ] Royalty-free music provided
- [ ] No music
- [ ] Music-forward (Reels/TikTok style)

---

## REVISION PROCESS

**Approval Required From:** _____________________________________

**Number of Revision Rounds:** __________________________________

**Review Format:** ____________________________________________
(Example: Owner reviews draft via shared link, 24-hour feedback window)

---

## CREDIT BUDGET ESTIMATE

| Clips | Credit Type | Credits Each | Subtotal |
|---|---|---|---|
| _____ clips | Gen-4.5 Turbo (draft) | 25 | _____ |
| _____ clips | Gen-4.5 Full (final) | 60 | _____ |
| 1 | Reference image | 10 | 10 |
| _____ | Audio (TTS + SFX) | ~5-15 each | _____ |
| _____ | 4K Upscale (per 10s) | ~20 | _____ |
| **TOTAL ESTIMATED** | | | **_____** |

*Always budget 1.5× estimated for retakes on critical clips*

---

## BRIEF APPROVAL

Before production begins, this brief must be confirmed by:

- [ ] Creative direction reviewed and approved
- [ ] Script reviewed and timed
- [ ] Shot list reviewed and approved
- [ ] Credit budget reviewed and approved
- [ ] Anti-AI rules applied to all prompts
- [ ] Workflow build plan ready

**Status:** DRAFT / APPROVED / IN PRODUCTION / DELIVERED

---

*Generated by the Your Company Virtual Office Video Studio*
*This document is confidential. Do not share externally without Owner S.