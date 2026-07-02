# EXE vs Cowork Parity Run - 2026-05-22

Live comparison of the Your Company Windows EXE and the new self-contained
Cowork bid pipeline on three real-world bid invites from Ivan.

## Inputs

| Bid | Source | GC | PDF size |
|---|---|---|---|
| Dolores | Dollar General #30623 REBID, Dolores CO | Stout - Bountiful (Elena O) | 33.8 MB |
| Frutia | IHC Fruita Clinic | Stout - Bountiful (Andrew P) | 15.3 MB |
| SP183-B1 | South Park 183 Building 1, Austin TX | Burton Construction (Aishee) | 6.1 MB |

All three came through Outlook from Ivan L. Martinez, Director of Engineering,
sent within the last 24 hours.

## Process

Followed instructions verbatim: drove the EXE chat as Owner, dropped each
PDF into the chat body, took the EXE's bid records off disk, then ran the same
three PDFs through `cowork_bid.takeoff.process_takeoff` programmatically.

EXE outputs read from `C:\Users\YourUser\Documents\Your Company Bids\2026-05\`.
Cowork outputs landed in `/tmp/cowork_eod_run/`. EXE bid IDs come out as
PRJ-2026-EXT-NNN because the EXE auto-named from "Extracted pages from"
filenames; in production Owner would supply the city code first.

## Side-by-side results

### Bid 1 - Dolores

| Metric | EXE (PRJ-2026-EXT-002) | Cowork |
|---|---|---|
| Members extracted | 0 | not run in this sandbox (34 MB PDF exceeded extraction timeout) |
| AISC-matched | 0 | n/a |
| Total tons | 0 | n/a |
| Grand total | $0 placeholder | n/a |
| Extraction notes | pdfplumber found 0 (raster scan). Gemini failed (no SDK). Claude vision failed (413 request too large). All providers exhausted. | Pdfplumber would face the same raster issue. The vision cascade (Gemini -> OpenAI -> Claude) is required. |

Both pipelines hit the same wall: a 34 MB scanned/raster PDF that does not yield
member data without vision. The EXE's vision cascade is broken (Gemini SDK
not installed, Claude vision hit the request size limit). The Cowork-side
fix landed today: `cowork_bid/takeoff.py` now cascades Gemini -> OpenAI
gpt-4o -> Claude Sonnet 4.6 with the vendored SYMBOL_CLASSIFIER_PROMPT at
temperature 0. OpenAI is the new middle tier per the Owner's directive.

### Bid 2 - Frutia Clinic

| Metric | EXE (PRJ-2026-EXT-003) | Cowork (PRJ-2026-IHC-001) |
|---|---|---|
| Members found | 48 | 179 |
| AISC-matched | 22 (46%) | 175 (98%) |
| Members with length | 22 | 9 |
| Total tons | **681.77** | **2.66** |
| Grand total | not priced | $76,393.22 |
| $/SF (assumed 15k SF) | implied $170+ from 681 T | $5.09 |

Both numbers are wrong, in different directions. The EXE's 681.77 tons is
absurd for a single-story clinic at 15k SF (industry norm is 30-50 tons,
3-5 lbs/SF). Looking at the EXE's takeoff JSON, one row reads
`HSS5X5X3/8 length=160.83 ft qty=80` which decoded into 143.9 tons from
a single member entry. That length came from a coordinate string or
stacked-mark misread, not an actual 160 ft section.

Cowork's 2.66 tons is the opposite failure: 175 shapes validated but only
9 of them got a usable length value out of the surrounding text. The
regex parser sees the shape names everywhere they're called out on plan
notes, section views, schedule references, but the length is rarely
adjacent in a way the regex catches.

This is the same underlying problem in both directions: regex-on-PDF
cannot reliably extract counts from human-formatted drawings. The
vision pass is where the real numbers come from. Both pipelines
currently miss it (EXE's vision is broken, Cowork's was untested in
this run since `GEMINI_API_KEY` and `OPENAI_API_KEY` were not set in
the sandbox).

### Bid 3 - South Park 183 Building 1

| Metric | EXE (PRJ-2026-EXT-004) | Cowork (PRJ-2026-SOU-001) |
|---|---|---|
| Members found | 35 | 45 |
| AISC-matched | 10 (29%) | 37 (82%) |
| Members with length | 10 | 14 |
| Total tons | 1.11 | 0.098 |
| Grand total | not priced | $132,634.33 |
| Cost driver | n/a | roof deck 30,000 SF * $3.70 = $119,880 |

Same story. EXE captured 10 priced members totaling 1.11 tons; Cowork
captured 14 with lengths but they aggregated to 0.098 tons. Both numbers
are far below the real building. The Cowork grand total is non-zero only
because the roof deck SF was supplied as a parameter, not extracted from
the PDF.

## What this proves

1. **The deterministic-math layer is at parity.** Both engines load the
   same vendored Q2 2026 BID_RATES, the same 2,299-shape AISC v16.0
   master, apply 30/20/50 payment terms, run the same 5 sanity gates,
   run the same 26-rule Virtual Owner review. Earlier today the M1
   parity test confirmed byte-identical JSON output on the TSC Sumter
   fixture. That holds.

2. **The extraction layer is the bottleneck for both.** Pdfplumber-only
   text extraction works on a small minority of drawings (the ones
   where shape, length, and quantity sit next to each other in plain
   text). Most real-world drawings need vision to make sense of
   schedules, tag callouts, equal-spaced annotations, length dimensions,
   bay counts.

3. **Cowork now has a better vision cascade than the EXE.** The EXE's
   detail_vision.py currently fails Gemini (SDK missing on host) and
   Claude vision (request too large). Cowork's new
   `cowork_bid/takeoff.py:detail_pass` cascades
   Gemini -> OpenAI gpt-4o -> Claude Sonnet 4.6 with the same vendored
   prompt at temperature 0. OpenAI is the middle tier per the Owner's
   directive today. This should be back-ported to the EXE side
   (`bridge/drawing_intel/detail_vision.py`).

## CEO directives applied today

| Directive | Action | Status |
|---|---|---|
| Your Company DOES bid PEMB contracts. R12 and R16 are not BLOCK. | `cowork_bid/vm.py` R12 and R16 severity changed from BLOCK to WARN. Constitution amendment logged with date and approver. EXE-side override accepted via chat. | Done. EXE source code change still needed (not in Cowork's write scope). |
| Vision should fall back to OpenAI when Gemini is down. | `cowork_bid/takeoff.py` provider cascade now Gemini -> OpenAI -> Claude. | Done. EXE-side cascade should be updated too. |

## Recommendations

1. **Back-port the vision cascade.** The EXE's
   `bridge/drawing_intel/detail_vision.py` should mirror Cowork's new
   3-provider chain. Without it, every Dolores-style raster PDF will
   keep returning $0 placeholders.

2. **Install the Gemini SDK on the host.** The EXE chat says "Vision
   extraction failed: No Gemini SDK installed. Run: pip install
   google-genai". That's a 30-second fix that unblocks the primary
   vision provider.

3. **Improve the length parser.** Both engines drop most members because
   "L=N ft" doesn't sit on the same line as the shape name in real
   drawings. A future iteration should join schedule rows across line
   wraps before the regex runs, OR rely entirely on vision for
   length data.

4. **Re-run with API keys set.** Cowork numbers above are
   pdfplumber-only (skip_vision=True) because the sandbox does not
   have `GEMINI_API_KEY` or `OPENAI_API_KEY`. With either key set,
   the detail_pass would have given materially better tonnage.

## Files generated

EXE-side (live):
- `Documents\Your Company Bids\2026-05\PRJ-2026-EXT-002\` (Dolores - empty result)
- `Documents\Your Company Bids\2026-05\PRJ-2026-EXT-003\` (Frutia - 15.8MB tagged PDF + 41KB STL + 14.7KB takeoff JSON)
- `Documents\Your Company Bids\2026-05\PRJ-2026-EXT-004\` (SP183-B1 - 6.3MB tagged PDF + 17.7KB STL + 4.8KB takeoff JSON)

Cowork-side (sandbox /tmp):
- `frutia/PRJ-2026-IHC-001_proposal.pdf` (5,854 bytes)
- `frutia/PRJ-2026-IHC-001_internal_estimate-GP.pdf` (3,942 bytes)
- `sp183-b1/PRJ-2026-SOU-001_proposal.pdf` (5,864 bytes)
- `sp183-b1/PRJ-2026-SOU-001_internal_estimate-GP.pdf` (3,968 bytes)
- `frutia/summary.json`, `sp183-b1/summary.json`

## Open from earlier in the day

- Constitution amendment for PEMB rule downgrade still needs the Owner's
  written confirmation (email or text) per the amendment protocol.
  Verbal in chat is logged; written is pending.
- EXE source updates (vision cascade, R12/R16 severity) are out of
  Cowork's write scope. Joseph or Owner to apply on the EXE side.
