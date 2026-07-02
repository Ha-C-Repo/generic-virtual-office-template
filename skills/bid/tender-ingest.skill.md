---
name: tender-ingest
version: 1.0.0
inputs:
  - tender_dir (path)
outputs:
  - tender-index.json
mcp_connectors:
  - filesystem
  - pdf-parser
voice: owner
---

# tender-ingest

## Purpose

Walk a tender package folder. Enumerate every file. For each PDF, extract
text and per-page anchors. Classify each file as drawing, spec, scope, or
head-contract. Emit `tender-index.json` with one row per source page.

## Inputs

`tender_dir`: absolute path to a folder containing the tender package.
PDFs, Word, Excel. Scanned or digital. No assumption about structure.

## Procedure (Sequential Thinking)

1. List every file in `tender_dir` recursively. Capture filename, size,
   modified-time.
2. For each PDF: invoke pdf-parser MCP. Capture per-page text and page
   number. If page text is empty or near-empty, mark `needs_ocr=true`.
3. For each Word/Excel: extract text with native readers.
4. Classify each document by filename keywords AND first-page content:
   - `drawings` if filename contains "DWG", "S-", "A-", or first page
     shows a title block.
   - `specs` if filename contains "spec", "section", "div", or first page
     shows a CSI division header.
   - `scope` if filename contains "scope", "SOW", "schedule of works".
   - `head_contract` if filename contains "contract", "agreement", "ITT",
     "tender conditions", "general conditions".
   - `other` otherwise.
5. Write `tender-index.json` to the bid project folder.

## Output schema

```
[
  {
    "doc_id": "DOC-0001",
    "filename": "Scope of Works.pdf",
    "class": "scope",
    "pages": 14,
    "needs_ocr": false,
    "page_text": [
      { "page": 1, "text": "..." },
      { "page": 2, "text": "..." }
    ]
  }
]
```

## Honest limits

- Scanned PDFs need OCR. Cowork uses Tesseract local fallback. Accuracy
  on scanned drops to 80-90% character-level. Flag `needs_ocr=true`.
- Drawing geometry (lines, symbols, dimensions) is NOT extracted by this
  skill. Use takeoff-completeness-check or LIFT for graphical takeoff.
- Tender packs >500 pages: chunk by document, not by page count.

## Hard rules respected

- No supplier names surfaced in any user-facing output of this skill.
- Output written only to the active bid project folder.
