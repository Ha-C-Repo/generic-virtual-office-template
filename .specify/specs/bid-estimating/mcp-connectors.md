# MCP Connectors - Bid Estimating

Two connectors register in the Cowork Customize/MCP panel. Both are
required for the skills under `skills/bid/` to operate end-to-end.

## Connector 1: filesystem

- Purpose: Read and write the schemas, skill outputs, rate library, and
  artifact templates.
- Scope: Restricted to the active bid project folder and its children:
  - `.specify/specs/bid-estimating/**`
  - `data/schemas/**`
  - `data/closed_bids/**`
  - `library/production-rates.yaml`
  - `artifacts/templates/**`
  - `scripts/**`
  - `handoff_backups/**`
  - `inbox/**`
  - Active bid project subfolder (path supplied at runtime).
- Out of scope: anywhere outside the project root. Never `API Keys/`.
  Never `__pycache__/`, `.git/`, `dist/`, `build/`, `*.pyc`, `*.log`.

## Connector 2: pdf-parser

- Primary path: M365 Word "Open PDF" or Google Docs PDF import. Both are
  inside the approved stack and produce reliable text + page anchors
  for digital PDFs.
- Fallback for scanned PDFs: local Tesseract OCR via
  `scripts/ocr_fallback.py` (not included by this delta; flagged as
  follow-up).
- Honest limit: neither M365 nor Google nor Tesseract delivers
  pixel-accurate beam counts on raster structural drawings. For that
  the only options are (a) SketchDeck LIFT, Beam AI, Togal.AI, or Kreo
  (all out-of-stack and flagged in the constitution delta), or (b)
  human estimator verification with Your Company's existing process.

## Not used by this workflow

- Runway AI: reserved for marketing visuals. Out of scope for bids.
- Operum.io, ContraVault, PinPoint Analytics: out-of-stack vendors
  referenced for benchmark only. Not connected.

## Registration steps (operator)

1. Open Cowork settings, Customize panel, MCP servers.
2. Add `filesystem` server with the scope above.
3. Add `pdf-parser` server pointing to the in-stack reader.
4. Run `self test` from the Chat tab to verify both servers respond.
5. Run `vj scan and fix` to validate the rest of the bridge.
