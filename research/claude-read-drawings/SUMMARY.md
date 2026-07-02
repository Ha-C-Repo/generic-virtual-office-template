# Claude Reads Construction Drawings (Tim Fairley / ContractorOS) - Summary

Source: one YouTube video, "How to Get Claude to Read Construction Drawings" by Tim Fairley (ContractorOS / "Contractor OS" community), watched 2026-07-02 at full depth (download, three 1024px frame windows of 100 frames each read in parallel, complete caption transcript). Per-video report beside this file: `ItW-ielFvGg.md`. Lens: what transfers to Your Company, a structural steel fabricator.

This is the 16th Tim Fairley / ConstructIQ video in our research and a direct follow-up to `research/constructiq-watch/_k1jQBS4Nk8.md` ("Claude Code + Construction Drawings"): same presenter, same Yatala QLD portal-frame warehouse example, same `drawings-analyser` skill. It belongs to the same channel KB as `research/constructiq-watch/`. A `docs/CONSTRUCTIQ-KB.md` is referenced in CLAUDE.md but does not exist yet; if that KB is built, this video and the constructiq-watch set are its source material. Adjacent KB: `docs/AISC-EDU-KB.md`.

## The one idea

Do not make AI read drawings. Run a one-time indexing pass that turns a PDF set into two queryable layers - a normalized SQLite database of the physical objects (grouped by object, not by sheet) and a Karpathy-style concept wiki of the notes/specs - sitting under a `drawings.md` map. Every row and every fact carries its source sheet and a reliability score; the skill validates its own provenance and flags conflicts as RFIs. Then queries read cheap structured text and drop to the source PDF page only when needed. This is his `drawings-analyser` Claude skill, now run in Claude Cowork (the prior video used Claude Code). It is, almost line for line, Your Company's verify-do-not-generate + per-line confidence + project-indexer design, arrived at from the general-construction direction on a structural-steel job.

## The numbers he reports (his own test set + blind grader; LOW confidence for us until reproduced)

- Test: a real 25-sheet warehouse structural set plus a plumbing set; three fresh AIs each given one version (raw images / prose notes / the database); a separate AI blind-graded; ground truth = the drawing text layer + a verified takeoff; 44 questions (28 + 16 harder); instance counts matched the human takeoff 14 of 14.
- Accuracy: raw images 86% (3 fabricated answers), prose notes 98% (0 fabricated), database 96% -> 100% after the provenance check (1 -> 0 fabricated).
- Tokens per question: read images 104,552, read text 66,219, query database 1,446. Database 46-72x cheaper (session scaling 46x / 201x / 348x at 1 / 5 / 10 questions), plus roughly 10x fewer tool calls (about 16 vs 157).
- Measured learnings: vision approx 40-55% on symbol counting vs vector text layer approx 100%; `validate_provenance.py` took a test DB 96.4% -> 100%.

These were legible on screen, so the transcription is reliable, but they are self-reported claims. Governance verify-do-not-generate: no number here may set a system-of-record value. AISC weights come only from `bridge/aisc_validator.py`, rates only from `bridge/bid_rates.py`.

## What transfers to Your Company (prioritized)

Adopt (high value, fits governance):
1. Object/mark-keyed takeoff store with `schedules` (catalogue, one row per type) vs `instances` (one row per placed object with a grid coordinate), each row carrying source sheet + confidence. This is our `bridge/takeoff_row.py` schema plus his schedule-vs-instance split, which is the same distinction our A1 schedule reader and Engine B grid geometry work with on `feature/count-gap-sf-a1`.
2. Provenance validation as a build-time gate: after a takeoff, re-verify every counted mark actually appears on the sheet it cites; relocate or flag mis-sourced rows. Deterministic, cheap, and squarely verify-do-not-generate. His `validate_provenance.py` is the model.
3. Report counts as "validated N/N against the takeoff," matching our reconciliation advisory gate (`reconcile_advisory()`).
4. Schema rule: store quantity as an explicit integer, never inline text like "F10 x2" (his learning #4 - an ambiguous notation caused a real miscount).
5. Concept-wiki + standing conflict/RFI register for the notes/specs layer (steel spec, bolt grade, weld standard routed to one page; conflicts auto-raised as RFIs). Same idea as our auto-RFI and completeness gate; his live catch was an office-slab 25-vs-32 MPa grade conflict.
6. Keep the confidence discipline explicit: schedule value or counted tag = HIGH; scaled area/length = MEDIUM and hedged, never stated as fact. Reinforces our SF-is-controlling rule (his summary: "no overall dimensions printed, all plan geometry rides on scale calibration").

Reject or guard (Tier 1 / accuracy):
- Do NOT treat his slab-area accuracy as evidence AI vision can size members. Bid-grade tonnage is a measured member takeoff through `aisc_validator.py`, never SF x psf or vision.
- Do NOT import his third-party skill code without a Dependency-tax review; the method transfers, the binary does not. Do not act on instructions embedded in his files.
- His numbers are self-reported; keep them out of any priced output.
- No supplier or rate data belongs in a cloud connector, regardless of his practice.

## Video index

| Video ID | Title | Duration | One-line takeaway | Report |
|---|---|---|---|---|
| ItW-ielFvGg | How to Get Claude to Read Construction Drawings | 18:55 | Index a drawing set into an object-keyed SQLite DB + Karpathy concept wiki under drawings.md, tag every row with source + reliability, validate provenance; 46-72x cheaper, 86/98/100% accuracy on his blind test | ItW-ielFvGg.md |

## Caveats

- Transcript is complete and reliable (captions, 538 segments). On-screen figures were read from 300 frames at 1024px and are reliable transcriptions of what the charts showed; the underlying claims are the presenter's own and are unverified by us.
- The example set is a real Australian job (Spencer Group Engineering, Yatala QLD); it is used illustratively and is not a Your Company project.
- The video-description skill link, the ContractorOS community, and any third-party code were not followed or imported.
