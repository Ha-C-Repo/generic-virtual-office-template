# Master Website Prompt

Copy, fill the brackets, paste as one message.

```
Use the frontend-design and web-build skills. Build a complete, award-quality
marketing website in a single pass. Plan the folder structure first, then build.

BUSINESS: [one sentence on what the company does]
AUDIENCE: [who visits and what they need]
PAGE JOB: [the single most important action a visitor takes]
AESTHETIC DIRECTION: [pick ONE extreme: brutally minimal / maximalist /
  retro-futuristic / luxury-refined / editorial / industrial / organic]
REFERENCE: [paste an Awwwards/FWA-quality URL OR point to references/<file>.png.
  Match its layout rhythm, type scale, and motion - NOT its content or brand.]
TYPOGRAPHY: distinctive pairing, no Inter/Roboto/Arial/system fonts/Space Grotesk.
  State the two fonts before coding.
MOTION: one orchestrated page-load reveal (staggered animation-delay) plus
  purposeful scroll/hover micro-interactions. CSS-only for HTML; Framer for React.
STACK: [single-file HTML+Tailwind artifact] OR
  [Next.js + Tailwind + shadcn/ui + Framer Motion full scaffold]
SECTIONS: hero (thesis statement, the most characteristic thing in this brand's
  world), [list the rest: services, proof, pricing, contact, etc.]
HERO VISUAL: [Runway pipeline render OR CSS gradient/mesh background. 1920x1080,
  no on-image text, matching the aesthetic.]
ACCESSIBILITY: WCAG AA contrast, semantic HTML, keyboard-navigable, alt text.
PERFORMANCE: lazy-load media, system-font fallback, no layout shift.
OUTPUT: write everything to outputs/[company-slug]/. Then take a screenshot,
  compare against the REFERENCE and the brief, and fix anything that reads
  generic or templated. Show me the folder tree before writing code.
```

Notes:
- Hero visuals route through the Runway pipeline first, CSS gradient/mesh second.
  No Higgsfield (intake Section 04 ruling).
- yourcompany.example.com live-site work is the exception: it follows
  Website Rebuild/BRAND_KIT_v2.md, not this prompt's typography line.
