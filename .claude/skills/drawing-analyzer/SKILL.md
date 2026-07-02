---
name: drawing-analyzer
description: Pre-process a construction drawing set so counts and lookups run against text, not pixels. Splits the merged PDF into one file per sheet, renders a high-resolution image per sheet, and extracts the PDF vector-data text layer, then counts tagged items from that text. Use when the user uploads a drawing set, asks to count fixtures or fittings, asks how many of a tagged item, or asks to read the drawings. Never measure scaled quantities from the image; the model gives approximate, not accurate, counts.
---

# Drawing Analyzer

## Principle
Do not use vision to take a measurement or a count. Use deterministic code on the file, count tags from the extracted text layer, state confidence, and have a human verify. The scaled measurement is done in dedicated takeoff software (ZZ Takeoff, PlanSwift), not here.

## Process
1. Run `scripts/split_and_extract.py INPUT.pdf out/ --dpi 300` to split the set, raise resolution, and extract the text layer per sheet.
2. To count a tagged item, pass `--count TAG` (for example `--count CU5`). Counting the tag string in the vector text is reliable; counting symbols by eye is not.
3. Build a classification index (sheet to discipline) and a cross-reference matrix from drawings.md.
4. For every returned item, state confidence: high if counted from a vector tag, low if only visually apparent.
5. Hand the result to a human to verify before it enters a price.

## Good uses
High-level conceptual estimating where some error is acceptable, generating the full list of measurable items for a human takeoff, and cross-checking a completed takeoff.

## Not for
System-of-record steel quantities. Use a dedicated takeoff tool or a human estimator.
