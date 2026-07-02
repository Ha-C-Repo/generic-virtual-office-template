---
name: owner-voice-check
description: >
  Final-pass voice check for any output going to Owner, going out
  under the Owner's name, or going to a client. Catches AI-isms,
  em-dashes, three-adjective lists, placeholder tokens, hedging
  language, and length-padding. Run this before any deliverable PDF,
  email draft, text reply, or LinkedIn post. Run silently and only
  surface findings if there are violations.
triggers:
  - voice check
  - owner voice
  - before sending
  - finalize draft
  - is this ready
  - review this email
  - review this text
  - copy-paste ready
  - check for ai-isms
---

# Owner Voice Check

This is a gate, not a generator. Run as the last step before any
artifact leaves the system. Block delivery on critical violations,
warn on minor ones, pass silently when clean.

## The kill list (any one = block)

### Em-dashes
The literal character `—` (U+2014) and the typographic dash `–`
(U+2013). Search-and-replace policy:
- `—` → `.` if it joins two complete clauses, otherwise `,`
- `–` → `-` (hyphen) when used as a separator
Auto-fix is safe here.

### Three-adjective lists
The pattern `<adj>, <adj>, and <adj>` where all three modify the
same noun. Example to flag: "solid, compelling, and impressive."
Owner accepts two: "solid and simple." Auto-fix: drop the
middle adjective unless it carries unique meaning, ask if unsure.

### "Not just X, it's Y" / "It's not X, it's Y"
Construction Owner explicitly rejects. Examples:
- "It's not just a bid, it's a partnership"
- "Not just steel, but reliability"
Auto-fix: remove the construction, restate the second clause directly.

### Hedging language
- "I'd be happy to..."
- "Great question!"
- "I think..."
- "It seems like..."
- "You might want to consider..."
- "Per our conversation"
- "I hope this helps"
Auto-fix: delete the hedge, keep the substance.

### Placeholder tokens
- `[insert name]`, `[name]`, `[client]`, `[date]`, `[address]`
- `<your contact>`, `<TBD>`, `<placeholder>`
- "Dear [Customer Name]"
Auto-fix: NONE. These must be resolved before send. If real values
aren't known, BLOCK the output and ask Owner for the fill-ins.

### Page-padding language
- "In conclusion,"
- "To summarize,"
- "As mentioned above,"
- "Furthermore,"
- "Moreover,"
- "It's worth noting that"
Auto-fix: delete the connector, keep the content.

## The warn list (surface but don't block)

### Sentence length
Average sentence > 22 words in body text. the Owner's own writing
averages 9-13. Flag and offer a tightened version.

### Adjective-to-noun ratio
> 0.4 adjectives per noun. Steel-industry copy should read like a
quote, not a brochure. Flag and offer a tightened version.

### Steel jargon in client-facing text where client is non-technical
Terms like "shop drawings," "K-zone," "PJP," "CJP," "AESS Cat 4"
when the recipient is a homeowner, restaurant owner, or
non-construction client. Pattern: client emails from gmail.com,
yahoo.com, hotmail.com → assume layperson.

### Engineering as a line item
The literal string "Engineering" or "Detailing" as a separately
priced row in a bid. Owner rule: fold into fab + erection. Flag
on bid PDFs, ignore on internal GP reports.

## The format kill list (PDF/document only)

### Logo placement
Logo must be top-left, 1.25" max height. Flag if center-aligned,
right-aligned, stretched, or larger than spec.

### Orphan paragraphs
Single line of body text at the bottom of a page with the rest of
the paragraph on the next page. Visual QC catches these. Flag and
recommend break adjustment.

### Text outside boxes
Anything that overflows its container or sits at a negative offset.
Flag with page number and approximate location.

### Dark figures on dark backgrounds
Charts, tables, or images where the foreground luminance is within
30% of the background luminance. Flag with page number.

### Blurry images
Resolution < 150 DPI on any embedded raster image. Flag with the
specific image's file or placement.

## Output contract

When run as a gate, the response shape is one of three:

1. **PASS** (clean): Return the input unchanged. Add no commentary.
   No "Looks good!" No "All checks passed." Silence on success.

2. **AUTO-FIX** (only kill-list items that have safe rewrites):
   Apply the fixes, return the corrected text, and append a short
   block under `--- voice-check applied ---` listing what changed.
   Format: one line per change, no bullets in the body.

3. **BLOCK** (placeholders unresolved, format errors on PDF):
   Return the input with a `--- voice-check blocked ---` block at
   the top listing the unresolved items. Do NOT proceed to delivery.

## Examples

### Block: placeholder unresolved
```
--- voice-check blocked ---
Unresolved placeholders: [Client Name], [Project Title]
Action: provide values before sending.
```

### Auto-fix: em-dash + hedge
Input:
> Great question — I'd be happy to help. Our scope starts at the top
> of the concrete piers.

Output:
> Our scope starts at the top of the concrete piers.
>
> --- voice-check applied ---
> Removed: "Great question — I'd be happy to help."
> Em-dash policy: deleted.

### Pass: silent
Input that's already clean returns unchanged with no annotation.

## Why this skill exists

Per the Owner's operating-style file: "Format errors he has to clean up.
Logo placement, blurry images, text overlapping boxes, dark colors
that hide figures, orphan paragraphs." Every cleanup pass is rework
he didn't ask for. This skill kills the rework loop by catching the
errors before they reach him. Apply consistently. Do not skip on
"quick" deliverables — those are the ones that ship with errors.
