---
name: proposal-format
description: >
  Locked PDF proposal format spec (April 28, 2026). Use when
  generating any bid proposal, GP report, or SOQ document.
triggers:
  - generate proposal
  - build the pdf
  - proposal format
  - bid document
---

# Proposal Format (Locked 04-28-2026)

## Cover page
1. Project title
2. PROPOSAL banner
3. Rendering from drawing set
4. Location below image
5. 4-column project facts table
6. PREPARED FOR / PREPARED BY blocks
7. Navy date strip
8. Contact info + logo at bottom

## Style spec
- NAVY: #1F2A44
- Font: Calibri throughout
- Body text: 9pt (size 18 in ReportLab)
- Page: US Letter, 1" L/R margins, 0.75" T/B
- Section headers: "01 | SECTION NAME" format, 26pt bold navy
- Table headers: navy fill, white text, bold

## Content pages (page 2+)
- Header: centered title, YOUR COMPANY left, date right
- Navy horizontal rule below header
- Logo: 144x32pt canvas at x=415, y=61pt
- Footer: navy rule, contact left, "Page X of Y" right

## GP report differences
- Red CONFIDENTIAL watermark (#B71C1C)
- Banner color: #8B0000
- KPI boxes on cover
- "Ivan to verify / Owner to approve" line
- Drawing stage + contingency % on cover

## Hard rules
- Literal & never &amp;
- Real logo file, never text placeholder
- Never shrink fonts to hit page count
- Never drop content to hit page count
- PDF only output
