# NC-QC-FAB-001 Checklist Reconciliation and Basis of Record

**Date:** 2026-06-18
**Status:** PROVISIONAL. The NC-QC-FAB-001 program PDF was not available in the
project. Per CEO direction (2026-06-18: "if not provided, plan and build what is
needed"), the three checklist constants below are finalized from the governing
standards and the Joseph brief, and are adopted as the working standard. They are
marked provisional only in the sense that they should be confirmed word for word
against NC-QC-FAB-001 Sections 4.1, 4.2, and 9 if that program is later provided.
The build does not wait on it.

What is already certain (no reconstruction needed): the 18 traveler fields match
the Joseph brief verbatim and the controlled Section 8 sequence, and all six hard
blocks are enforced. Only the two receiving checklists and the NCR category list
were not enumerated in the brief, so only those are reconstructed here.

## 1. Gate 1 MTR review checklist (program Section 4.1)

Adopted items, each tied to its basis. Lives in `shopqc/ui/receiving.py` (MTR_CHECKS).

| # | Checklist item | Basis |
|---|---|---|
| 1 | Heat number on steel matches MTR | AISC 207-25 material traceability; ASTM A6 marking |
| 2 | ASTM spec and grade conform to PO (A992 / A500 / A36 / F1554) | Purchase-order conformance; project structural notes |
| 3 | Fy meets specified minimum | ASTM A992/A500/A36 mechanical properties |
| 4 | Fu meets specified minimum | ASTM A992/A500/A36 mechanical properties |
| 5 | Carbon equivalent (CE) within limit | ASTM A992 supplementary CE; weldability control |
| 6 | MTR legible and on file | AISC 207-25 records retention |
| 7 | Country of origin recorded | Buy-clause / project spec where applicable |

Adopted as written. No change recommended absent the program text.

## 2. Gate 1 physical receiving checklist (program Section 4.2)

Lives in `shopqc/ui/receiving.py` (PHYS_CHECKS).

| # | Checklist item | Basis |
|---|---|---|
| 1 | Piece count matches BOL | Receiving control |
| 2 | Section size verified by measurement | AISC 207-25 receiving inspection |
| 3 | No visible damage (bends, gouges, torch marks) | AISC 207-25; ASTM A6 surface condition |
| 4 | Straightness / sweep within AISC 303-22 tolerance | AISC 303-22 mill/fabrication tolerances |
| 5 | Surface condition acceptable (rust, pitting, mill scale) | ASTM A6; SSPC where coating applies |
| 6 | Lengths spot-checked against BOL | Receiving control |

Adopted as written. One optional addition to consider when the program is seen:
a line confirming joist/joist-girder bundle tags and SJI mill tags for joist
deliveries, given the joist scope. Hold pending program text; do not add silently.

## 3. NCR categories (program Section 9)

Lives in `shopqc/db.py` (NCR_CATEGORIES). Seven categories.

| # | Category | Basis |
|---|---|---|
| 1 | Material nonconformance | ASTM / MTR conformance failure |
| 2 | Dimensional | AISC 303-22 tolerance failure |
| 3 | Welding | AWS D1.1 weld defect |
| 4 | Coating / surface prep | DFT / SSPC failure |
| 5 | Documentation | Missing or illegible record |
| 6 | Damage / handling | Transit or shop damage |
| 7 | Unauthorized field modification | Elite Crossing incident; requires EOR sealed reference before close (hard block 6) |

Adopted as written. Category 7 is load-bearing for hard block 6 and ties directly
to the Elite Crossing field-modification deflection issue. Do not rename or remove.

## 4. 18 traveler fields (program Section 8) - confirmed, not reconstructed

The 18 fields in `shopqc/db.py` (TRAVELER_FIELDS) match the Joseph brief verbatim,
including field 8 pre-weld CWI as the hard block and fields 15-18 at release. The
sequence is the controlled order and is not changed. The joist variant (K1) adds a
parallel SJI field set; it does not alter these 18.

## 5. Action if NC-QC-FAB-001 is later provided

Run prompt C2: compare each list above to the program Sections 4.1, 4.2, 9 verbatim,
change only the display strings (data, not logic) where they differ, keep the smoke
test green, and flip this document from PROVISIONAL to CONFIRMED with the date.
