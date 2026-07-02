# Your Company - Logo and Brand Mark Rules

The Your Company logo is the lowercase "your company" wordmark with the
isometric cube glyph. It is fixed. It is reproduced from the approved master
files only, never recreated.

## The one hard rule

Never change the logo. Do not alter the font, letterforms, letter spacing,
proportions, the cube geometry, or the orientation. Do not recreate the
wordmark in any typeface. Do not stretch, rotate, skew, recolor the mark,
outline it, add shadows or effects, or substitute a lookalike.

The only thing that may change is the background color behind the mark,
selected to suit the logo.

## Approved master files (brand/logos/)

- `your company.png` - black mark on transparent. Use on light backgrounds.
- `Your Company LLC.png` - silver mark on dark. Use on dark backgrounds.
- `your company.pdf`, `Your Company LLC.pdf` - vector masters for print.
- `your company.jpg` - raster fallback, white background only.

## Background pairing

- Light background: use the black mark (`your company.png`).
- Dark background: use the silver-on-dark lockup (`Your Company LLC.png`).
- Never place the black mark on a dark panel, and never invert or recolor a
  mark by hand to fit a background. Change the background instead, or pick the
  correct master for that background.

## Where this applies

Everywhere the logo is used: bids, proposals, GP reports, brochures, renders,
slides, the website, email, social posts, signage, and any other visual.

This is a Tier 1 brand rule. It does not get overridden.
## Machine-readable companion

`brand/brand-tokens.json` encodes this rule set plus the approved palettes,
lockup paths, and the Tier 1 DON'Ts as tokens for tooling.
`validate_bid_output.py` reads its `donts` block before any client PDF
export. This prose file remains the rule of record; on any conflict, this
file wins. Update both in the same commit.
