---
name: web-build
description: Build production web pages with a fixed stack and QA loop. Use when
  the user asks to build a website, landing page, or marketing site.
---
# Web Build

## Stack (default)
- Fast artifact: single-file HTML + Tailwind (CDN) + vanilla JS.
- Full project: Next.js + Tailwind + shadcn/ui + Framer Motion.
- Choose fast artifact unless the brief says "full project."

## Design tokens
- All color, type, spacing, radius as CSS variables / Tailwind theme.
- 2-3 colors max: one dominant, one ink, one sharp accent. No timid palettes.
- Type scale with intentional jumps (e.g., 1rem / 1.5 / 2.5 / 4 / 6).

## Typography rules
- Two fonts only. Pair display + body. Load from Google Fonts.
- Never Inter/Roboto/Arial/system/Space Grotesk on NEW builds.
- Exception: yourcompany.example.com live-site work follows Website Rebuild/BRAND_KIT_v2.md
  (Archivo display + Inter body), approved by Owner 2026-06-10. That kit wins.

## Animation
- One orchestrated entrance (staggered animation-delay). Purposeful scroll/hover.
- CSS-only for HTML; Framer Motion for React. No motion without a reason.

## Responsive
- Mobile-first. Test 360 / 768 / 1280. No horizontal scroll.

## Accessibility
- WCAG AA contrast both themes. Semantic landmarks. Focus rings. Alt text.

## Performance
- Lazy-load below-fold media. No layout shift. Inline critical CSS for artifacts.

## Output + QA loop
- Write to outputs/<company-slug>/.
- After building: screenshot, compare to brief + reference, list what reads
  generic, fix it. Repeat until distinctive.

## Anti-slop guardrails
- No generic SaaS card grid as the first impression.
- No carousel without narrative purpose.
- Numbered markers (01/02/03) only if content is a real sequence.
- Never invent facts, pricing, or claims. brand.md + brief only.
- No em-dashes anywhere in copy. Hyphens or periods only.
- No supplier names, margins, or precedent-project claims in any Your Company
  outward copy. Sanitizer rules apply to website copy.
