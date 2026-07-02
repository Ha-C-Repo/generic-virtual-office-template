"""T10 revision diff: changed regions between two issues of one sheet.

Input is two issues of the same sheet (old PDF page, new PDF page),
usually an original set and an addendum reissue. Two passes:

  VECTOR  word-level diff of the text objects: added, removed, and
          changed designations, each with bboxes. Matched words also
          yield a median displacement so a wholesale title-block shift
          does not read as ten thousand moves; the median is computed
          from words UNIQUE on both issues, which identical-token
          mispairing cannot corrupt. The member callout delta is
          counted by a census-grammar sweep of BOTH full pages, never
          derived from the pairing heuristics, so a mis-paired word
          cannot corrupt a count.
  PIXEL   rasterize both pages (PyMuPDF, 2x), align by phase
          correlation, absolute difference, threshold, contour the
          changed regions with OpenCV. Catches geometry changes the
          text diff cannot see: moved gridlines, new members drawn,
          erased details, clouding.

Outputs:
  A  a copy of the NEW issue PDF with red boxes on every changed
     region, saved with the suffix _DIFF. Pixel regions are all
     drawn; vector boxes are drawn for changed pairs and for
     designation-bearing added, removed, and relocated words (every
     text change already sits inside a red pixel region, so drawing
     all added words would only bury the callouts that matter).
     Internal working surface, never for issue.
  B  takeoff_delta.md listing member callouts added or removed per
     sheet so census.db and the takeoff xlsx can be updated and
     re-stamped (hash recipe per takeoff_hash.py, schema 13.2).

If either input page is scanned/non-vector (sheet_router word-count
rule), the vector pass is skipped for that sheet, the report says so,
and the sheet runs pixel-only.

Confidence follows the census convention (P24): designation deltas
from plan text are medium, pixel-only regions are low. Nothing from
this module is high confidence: a diff is evidence for a human
re-take, never a count of record (verify, do not generate).

Free tooling only (PyMuPDF, OpenCV, numpy). No em-dashes in any
generated text. Standalone: no bridge/ imports. The designation
grammar comes from census.py, never duplicated. All page numbers in
the CLI and the report are 1-based; the Python API is 0-based like
PyMuPDF.
"""

import logging
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from takeoff_pipeline import census, sheet_router
from takeoff_pipeline.overlay import sheet_key

log = logging.getLogger("takeoff_pipeline.revision_diff")

_PKG = Path(__file__).resolve().parent
# Backup landing zone per the repo operating rule; module-level so
# tests can point it at a sandbox instead of the live changelog.
HANDOFF_ROOT = _PKG.parent / "_handoff"

ZOOM = 2.0  # rasterization scale per the T10 prompt
# Gray levels of absolute difference below this are antialias jitter
# between two renders, not a drawing change.
PIXEL_THRESHOLD = 60
# Contour bounding boxes smaller than this many square PDF points are
# raster speckle, not drawing changes.
MIN_REGION_PT2 = 12.0
# Changed-region rects closer than this many points merge into one box.
MERGE_PAD_PT = 4.0
# Caps so a wholesale redraw cannot produce an unusable overlay. Every
# applied cap is counted and reported, never silent.
MAX_REGIONS_PER_SHEET = 400
MAX_RAW_BOXES_BEFORE_MERGE = 2000
MAX_CHANGED_ANNOTS = 300
# A matched word deviating from the sheet's median displacement by
# more than this many points counts as relocated.
MOVE_TOL_PT = 9.0
# Unmatched old and new words closer than this (after shift
# correction) pair as one changed token instead of an addition plus a
# removal. A designation swap sits at the same callout location.
CHANGE_PAIR_TOL_PT = 25.0
# Above this many candidate old x new leftover combinations the
# changed-pair search is skipped (reported, not silent) and leftovers
# stay plain added or removed.
MAX_CHANGE_PAIR_CANDIDATES = 2_000_000
# Alignment shifts beyond this fraction of the page are rejected: two
# issues of one sheet do not move that far, a bad phase lock does.
MAX_SHIFT_FRACTION = 0.15

RED = (0.85, 0.05, 0.05)
_INTERNAL_MARK = "REVISION DIFF - INTERNAL - NOT FOR ISSUE"

MODE_FULL = "vector+pixel"
MODE_PIXEL_ONLY = "pixel_only"

# sheet_router's sheet-id grammar covers the dotted scheme (S2.1).
# Hyphenated title blocks (S-501) fall through it, so pairing carries
# a fallback scan of the bottom-right strip for the hyphenated form.
_HYPHEN_ID = re.compile(r"^[A-Z]{1,3}-\d{2,3}[A-Z]?$")


# -- sheet pairing ----------------------------------------------------------

def _sheet_id(page) -> str:
    """Sheet number of one page: title-block parse first, then the
    visually bottom-right strip scanned for a hyphenated id. Word
    bboxes live in the unrotated space, so on a /Rotate page they map
    through the rotation matrix before the strip test (the title
    block is bottom-right as displayed, not as stored)."""
    import fitz

    parsed = sheet_router.parse_title_block(page)
    if parsed["sheet_number"]:
        return parsed["sheet_number"]
    rect = page.rect
    rot = page.rotation_matrix if page.rotation else None
    cands = []
    for w in page.get_text("words"):
        if not _HYPHEN_ID.match(w[4].upper()):
            continue
        r = fitz.Rect(w[:4])
        if rot:
            r = (r * rot).normalize()
        if r.x0 > rect.width * 0.80 and r.y0 > rect.height * 0.75:
            cands.append((r.y0, r.x0, w[4].upper()))
    if not cands:
        return ""
    cands.sort(key=lambda t: (-t[0], -t[1]))
    return cands[0][2]


def pair_sheets(old_pdf, new_pdf) -> dict:
    """Pair pages across two issues by sheet number.

    A sheet number seen on more than one page of one file is
    ambiguous: pairing it is guesswork, so it is dropped and reported
    (surface uncertainty, never guess). Pages with no readable sheet
    number simply do not pair; force them with explicit pairs."""
    import fitz

    def inventory(path):
        mapping, ambiguous = {}, set()
        doc = fitz.open(str(path))
        try:
            for i, page in enumerate(doc):
                sid = _sheet_id(page)
                if not sid:
                    continue
                if sid in mapping and mapping[sid] != i:
                    ambiguous.add(sid)
                else:
                    mapping.setdefault(sid, i)
        finally:
            doc.close()
        for sid in ambiguous:
            mapping.pop(sid, None)
        return mapping, ambiguous

    old_map, old_amb = inventory(old_pdf)
    new_map, new_amb = inventory(new_pdf)
    common = sorted(set(old_map) & set(new_map), key=sheet_key)
    # A sheet ambiguous in one file may still be unique in the other;
    # listing it as only-in-that-issue would be false. Ambiguous is
    # its whole story.
    amb = old_amb | new_amb
    return {
        "pairs": [{"sheet": sid, "old_page": old_map[sid],
                   "new_page": new_map[sid]} for sid in common],
        "old_only": sorted(set(old_map) - set(new_map) - amb,
                           key=sheet_key),
        "new_only": sorted(set(new_map) - set(old_map) - amb,
                           key=sheet_key),
        "ambiguous": sorted(amb, key=sheet_key),
    }


# -- vector pass ------------------------------------------------------------

def _page_words(page) -> list:
    """(text, bbox) per word. Kept word-level because word granularity
    is stable across re-exports while span splits are not."""
    return [(w[4], (w[0], w[1], w[2], w[3]))
            for w in page.get_text("words") if w[4].strip()]


def _page_spans(page) -> list:
    """(text, bbox) per text span. Matches the census sweep surface
    (kept local so the census private helpers stay private)."""
    out = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "")
                if txt.strip():
                    out.append((txt, tuple(span.get("bbox",
                                                    (0, 0, 0, 0)))))
    return out


def _designations_in(text: str) -> list:
    """Designation-family matches in one text, census grammar."""
    return [matched for family, _hint, matched, _span
            in census.sweep_text(text) if family == "designation"]


def _center(bbox):
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _pair_changed(old_left, new_left, shift):
    """Greedy nearest pairing of unmatched old vs new words within
    CHANGE_PAIR_TOL_PT (after median-shift correction). Returns
    (changed, removed, added). Texts always differ inside a pair:
    identical texts were consumed by the exact-match stage."""
    if not old_left or not new_left:
        return [], list(old_left), list(new_left)
    cands = []
    for i, (_ot, ob) in enumerate(old_left):
        oc = (_center(ob)[0] + shift[0], _center(ob)[1] + shift[1])
        for j, (_nt, nb) in enumerate(new_left):
            nc = _center(nb)
            d = math.hypot(nc[0] - oc[0], nc[1] - oc[1])
            if d <= CHANGE_PAIR_TOL_PT:
                cands.append((d, i, j))
    cands.sort()
    used_i, used_j = set(), set()
    changed = []
    for d, i, j in cands:
        if i in used_i or j in used_j:
            continue
        used_i.add(i)
        used_j.add(j)
        changed.append({
            "old_text": old_left[i][0], "new_text": new_left[j][0],
            "old_bbox": old_left[i][1], "new_bbox": new_left[j][1],
            "distance_pt": round(d, 1),
        })
    removed = [old_left[i] for i in range(len(old_left))
               if i not in used_i]
    added = [new_left[j] for j in range(len(new_left))
             if j not in used_j]
    return changed, removed, added


def _vector_diff(old_words, new_words) -> dict:
    """Word-level text diff: added, removed, changed, relocated."""

    def norm(t):
        return " ".join(t.split()).upper()

    old_by_text = {}
    for i, (t, _b) in enumerate(old_words):
        old_by_text.setdefault(norm(t), []).append(i)
    new_by_text = {}
    for j, (t, _b) in enumerate(new_words):
        new_by_text.setdefault(norm(t), []).append(j)

    matched_old, matched_new = set(), set()
    pair_disp = []
    unique_disp = []
    for key, new_idxs in new_by_text.items():
        pool = old_by_text.get(key, [])
        if not pool:
            continue
        if min(len(new_idxs), len(pool)) > 400:
            # Hundreds of identical tokens (dimension ticks, grid
            # bubbles): geometric pairing is quadratic there, and one
            # inserted instance offsets every positional pair, so
            # these pairs carry no displacement truth. Bookkeeping
            # only: marked matched, excluded from the median and the
            # moved test.
            for j, i in zip(sorted(new_idxs), sorted(pool)):
                matched_old.add(i)
                matched_new.add(j)
            continue
        # Smallest distance first, so identical locations pair at
        # zero and an inserted instance cannot cascade-shift the rest
        # of its family one slot over.
        cands = []
        for j in new_idxs:
            nc = _center(new_words[j][1])
            for i in pool:
                oc = _center(old_words[i][1])
                cands.append(((nc[0] - oc[0]) ** 2
                              + (nc[1] - oc[1]) ** 2, j, i))
        cands.sort()
        used_j, used_i = set(), set()
        for _d, j, i in cands:
            if j in used_j or i in used_i:
                continue
            used_j.add(j)
            used_i.add(i)
            matched_old.add(i)
            matched_new.add(j)
            oc = _center(old_words[i][1])
            nc = _center(new_words[j][1])
            disp = (nc[0] - oc[0], nc[1] - oc[1])
            pair_disp.append((i, j, disp[0], disp[1]))
            if len(new_idxs) == 1 and len(pool) == 1:
                unique_disp.append(disp)

    # Median displacement from words unique on both issues when any
    # exist: identical-token mispairing cannot reach those, so a
    # repeated dimension string can never fake a page shift.
    basis = unique_disp or [(d[2], d[3]) for d in pair_disp]
    if basis:
        shift = (median(d[0] for d in basis),
                 median(d[1] for d in basis))
    else:
        shift = (0.0, 0.0)

    moved = [(i, j) for i, j, ddx, ddy in pair_disp
             if math.hypot(ddx - shift[0], ddy - shift[1]) > MOVE_TOL_PT]
    moved_designations = []
    for i, j in moved:
        text = new_words[j][0]
        if _designations_in(text):
            moved_designations.append({
                "text": text,
                "old_bbox": old_words[i][1],
                "new_bbox": new_words[j][1],
            })

    old_left = [w for idx, w in enumerate(old_words)
                if idx not in matched_old]
    new_left = [w for idx, w in enumerate(new_words)
                if idx not in matched_new]
    pair_overflow = (len(old_left) * len(new_left)
                     > MAX_CHANGE_PAIR_CANDIDATES)
    if pair_overflow:
        log.warning("changed-pair search skipped: %d x %d leftover "
                    "words", len(old_left), len(new_left))
        changed, removed, added = [], list(old_left), list(new_left)
    else:
        changed, removed, added = _pair_changed(old_left, new_left,
                                                shift)
    return {
        "added": [{"text": t, "bbox": b} for t, b in added],
        "removed": [{"text": t, "bbox": b} for t, b in removed],
        "changed": changed,
        "moved_count": len(moved),
        "moved_designations": moved_designations,
        "median_shift_pt": (round(shift[0], 2), round(shift[1], 2)),
        "pair_overflow": pair_overflow,
    }


def _designation_counts(page) -> dict:
    """Census-grammar designation census of one page, keyed by
    normalized designation. Span-level like the census itself, so a
    multi-word callout (PL 1/4 X 10) counts the same way here as in
    census.db."""
    out = {}
    for txt, bbox in _page_spans(page):
        for family, hint, matched, _span in census.sweep_text(txt):
            if family != "designation":
                continue
            key = census.normalize_designation(matched)
            slot = out.setdefault(key, {
                "designation": matched.strip(),
                "item_class": census.classify_hit(hint, ""),
                "count": 0,
                "bboxes": [],
            })
            slot["count"] += 1
            if len(slot["bboxes"]) < 3:
                slot["bboxes"].append(
                    tuple(round(v, 1) for v in bbox))
    return out


def _callout_delta(old_page, new_page) -> list:
    """Member callout delta per designation: full-page census-grammar
    counts on each issue, then the difference. Plan text, so medium
    confidence per the census convention."""
    old_counts = _designation_counts(old_page)
    new_counts = _designation_counts(new_page)
    rows = []
    for key in sorted(set(old_counts) | set(new_counts)):
        o = old_counts.get(key)
        n = new_counts.get(key)
        oc = o["count"] if o else 0
        nc = n["count"] if n else 0
        if oc == nc:
            continue
        info = n or o
        rows.append({
            "designation": info["designation"],
            "item_class": info["item_class"],
            "old_count": oc,
            "new_count": nc,
            "delta": nc - oc,
            "where_issue": "new" if n else "old",
            "where_bbox": info["bboxes"][0],
            "confidence": "medium",
        })
    rows.sort(key=lambda r: (-abs(r["delta"]), r["designation"]))
    return rows


# -- pixel pass -------------------------------------------------------------

def _render_gray(page):
    """Grayscale raster at ZOOM. The pixmap is the ROTATED display;
    text extraction and annotations live in the unrotated page space,
    so pixel rects divide by ZOOM and then derotate (verified
    empirically on PyMuPDF 1.27: a /Rotate 90 page reports a word at
    its unrotated coordinates while the pixmap shows it rotated)."""
    import fitz
    import numpy as np

    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM),
                          colorspace=fitz.csGRAY, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8)
    return img.reshape(pix.height, pix.stride)[:, :pix.width].copy()


def _estimate_shift(old_img, new_img):
    """Translation of new relative to old by phase correlation, run on
    a downscaled copy (a full-res FFT of a 26 megapixel sheet spends
    memory measuring a shift that is a fraction of a point). Returns
    (dx, dy, response) in full-resolution pixels."""
    import cv2
    import numpy as np

    scale = min(1.0, 1600.0 / max(old_img.shape))
    if scale < 1.0:
        o = cv2.resize(old_img, None, fx=scale, fy=scale,
                       interpolation=cv2.INTER_AREA)
        n = cv2.resize(new_img, None, fx=scale, fy=scale,
                       interpolation=cv2.INTER_AREA)
    else:
        o, n = old_img, new_img
    win = cv2.createHanningWindow((o.shape[1], o.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(
        np.float32(o), np.float32(n), win)
    return dx / scale, dy / scale, float(response)


def _merge_regions(rects, pad):
    """Union-merge rects that overlap or sit within pad points."""
    merged = []
    pending = [list(r) for r in rects]
    while pending:
        r = pending.pop()
        hit = None
        for m in merged:
            if not (r[2] + pad < m[0] or m[2] + pad < r[0]
                    or r[3] + pad < m[1] or m[3] + pad < r[1]):
                hit = m
                break
        if hit is None:
            merged.append(r)
        else:
            merged.remove(hit)
            pending.append([min(r[0], hit[0]), min(r[1], hit[1]),
                            max(r[2], hit[2]), max(r[3], hit[3])])
    return [tuple(r) for r in merged]


def _pixel_diff(old_page, new_page) -> dict:
    """Aligned absolute-difference contours between the two renders,
    reported in new-issue page points (unrotated annotation space)."""
    import cv2
    import fitz
    import numpy as np

    rotation_mismatch = old_page.rotation != new_page.rotation
    if rotation_mismatch:
        log.warning("page rotations differ (old %d, new %d); the "
                    "renders are oriented differently and the diff "
                    "will over-flag", old_page.rotation,
                    new_page.rotation)
    old_img = _render_gray(old_page)
    new_img = _render_gray(new_page)
    resized = False
    if old_img.shape != new_img.shape:
        old_img = cv2.resize(
            old_img, (new_img.shape[1], new_img.shape[0]),
            interpolation=cv2.INTER_AREA)
        resized = True

    dx, dy, response = _estimate_shift(old_img, new_img)
    h, w = new_img.shape
    shift_rejected = (abs(dx) > MAX_SHIFT_FRACTION * w
                      or abs(dy) > MAX_SHIFT_FRACTION * h)
    if shift_rejected:
        log.warning("alignment shift rejected: dx=%.1f dy=%.1f px "
                    "(response %.3f); diffing unaligned", dx, dy,
                    response)
        dx = dy = 0.0
    if dx or dy:
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        old_img = cv2.warpAffine(
            old_img, m, (w, h), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=255)

    a = cv2.GaussianBlur(old_img, (3, 3), 0)
    b = cv2.GaussianBlur(new_img, (3, 3), 0)
    _, mask = cv2.threshold(cv2.absdiff(a, b), PIXEL_THRESHOLD, 255,
                            cv2.THRESH_BINARY)
    changed_fraction = float(np.count_nonzero(mask)) / mask.size
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    derot = new_page.derotation_matrix if new_page.rotation else None
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        rect = (x / ZOOM, y / ZOOM, (x + bw) / ZOOM, (y + bh) / ZOOM)
        if derot is not None:
            r = (fitz.Rect(rect) * derot).normalize()
            rect = (r.x0, r.y0, r.x1, r.y1)
        area = (rect[2] - rect[0]) * (rect[3] - rect[1])
        if area >= MIN_REGION_PT2:
            boxes.append((area, rect))
    raw_count = len(boxes)
    dropped_premerge = 0
    if len(boxes) > MAX_RAW_BOXES_BEFORE_MERGE:
        boxes.sort(reverse=True)
        dropped_premerge = len(boxes) - MAX_RAW_BOXES_BEFORE_MERGE
        boxes = boxes[:MAX_RAW_BOXES_BEFORE_MERGE]
        log.warning("pixel pass: %d smallest raw regions dropped "
                    "before merging", dropped_premerge)

    merged = [((r[2] - r[0]) * (r[3] - r[1]), r)
              for r in _merge_regions([r for _, r in boxes],
                                      MERGE_PAD_PT)]
    merged.sort(reverse=True)
    dropped_cap = 0
    if len(merged) > MAX_REGIONS_PER_SHEET:
        dropped_cap = len(merged) - MAX_REGIONS_PER_SHEET
        merged = merged[:MAX_REGIONS_PER_SHEET]
        log.warning("pixel pass: %d smallest merged regions over the "
                    "%d cap dropped", dropped_cap,
                    MAX_REGIONS_PER_SHEET)

    return {
        "regions": [r for _, r in merged],
        "areas": [round(a, 1) for a, _ in merged],
        "shift_pt": (round(dx / ZOOM, 2), round(dy / ZOOM, 2)),
        "response": round(response, 3),
        "shift_rejected": shift_rejected,
        "changed_fraction": round(changed_fraction, 5),
        "resized": resized,
        "rotation_mismatch": rotation_mismatch,
        "raw_region_count": raw_count,
        "dropped_small_premerge": dropped_premerge,
        "dropped_over_cap": dropped_cap,
    }


# -- per-sheet diff ---------------------------------------------------------

def diff_pair(old_doc, old_index, new_doc, new_index,
              sheet="") -> dict:
    """Diff one old/new page pair. Page indexes are 0-based."""
    old_page = old_doc[old_index]
    new_page = new_doc[new_index]
    old_wc = len(old_page.get_text("words"))
    new_wc = len(new_page.get_text("words"))

    reasons = []
    if sheet_router.is_scanned(old_wc):
        reasons.append(
            f"old issue page {old_index + 1} is scanned or non-vector "
            f"({old_wc} text words, threshold "
            f"{sheet_router.SCANNED_TEXT_THRESHOLD})")
    if sheet_router.is_scanned(new_wc):
        reasons.append(
            f"new issue page {new_index + 1} is scanned or non-vector "
            f"({new_wc} text words, threshold "
            f"{sheet_router.SCANNED_TEXT_THRESHOLD})")
    pixel_only = bool(reasons)

    result = {
        "sheet": sheet or f"PAGE-{new_index + 1}",
        "old_page": old_index,
        "new_page": new_index,
        "old_word_count": old_wc,
        "new_word_count": new_wc,
        "mode": MODE_PIXEL_ONLY if pixel_only else MODE_FULL,
        "pixel_only_reasons": reasons,
        "vector": None,
        "callout_delta": None,
    }
    if not pixel_only:
        result["vector"] = _vector_diff(_page_words(old_page),
                                        _page_words(new_page))
        result["callout_delta"] = _callout_delta(old_page, new_page)
    result["pixel"] = _pixel_diff(old_page, new_page)
    return result


# -- output A: the _DIFF overlay --------------------------------------------

def _add_box(page, rect, title, content, width=1.2, dashes=None):
    import fitz

    r = fitz.Rect(rect).normalize()
    r = r & page.rect
    if r.is_empty or r.is_infinite:
        return 0
    annot = page.add_rect_annot(r)
    annot.set_colors(stroke=RED)
    if dashes:
        annot.set_border(width=width, dashes=dashes)
    else:
        annot.set_border(width=width)
    annot.set_info(title=title, content=content)
    annot.update()
    return 1


def _annotate_page(page, result) -> dict:
    """Red boxes on one new-issue page. Returns draw counts."""
    import fitz

    drawn = {"pixel": 0, "changed": 0, "added": 0, "removed": 0,
             "moved": 0, "changed_capped": 0}
    pixel = result["pixel"]
    total = len(pixel["regions"])
    for k, (rect, area) in enumerate(
            zip(pixel["regions"], pixel["areas"]), start=1):
        drawn["pixel"] += _add_box(
            page, rect, "changed region (pixel pass)",
            (f"changed region {k} of {total}\n"
             f"area {area:.0f} sq pt\n"
             "confidence: low (pixel evidence only)\n"
             "geometry or text differs from the old issue; "
             "verify by eye"),
            width=1.8)

    vec = result["vector"]
    if vec:
        shift = vec["median_shift_pt"]
        for item in vec["changed"]:
            if drawn["changed"] >= MAX_CHANGED_ANNOTS:
                drawn["changed_capped"] += 1
                continue
            drawn["changed"] += _add_box(
                page, item["new_bbox"], "changed text",
                (f"was: {item['old_text']}\n"
                 f"now: {item['new_text']}\n"
                 "confidence: medium (vector text)\n"
                 "verify the callout and the takeoff row"))
        for item in vec["added"]:
            if not _designations_in(item["text"]):
                continue
            drawn["added"] += _add_box(
                page, item["bbox"], "added callout",
                (f"added in this issue: {item['text']}\n"
                 "confidence: medium (vector text)\n"
                 "add to the takeoff after verification"))
        for item in vec["removed"]:
            bbox = item["bbox"]
            at = (bbox[0] + shift[0], bbox[1] + shift[1],
                  bbox[2] + shift[0], bbox[3] + shift[1])
            if not _designations_in(item["text"]):
                continue
            drawn["removed"] += _add_box(
                page, at, "removed callout",
                (f"removed in this issue: {item['text']}\n"
                 "box drawn at the old-issue location\n"
                 "confidence: medium (vector text)\n"
                 "remove from the takeoff after verification"),
                dashes=[4, 3])
        for item in vec["moved_designations"]:
            drawn["moved"] += _add_box(
                page, item["new_bbox"], "relocated callout",
                (f"relocated: {item['text']}\n"
                 "confidence: medium (vector text)\n"
                 "count unchanged unless the delta table says "
                 "otherwise; verify the new location"),
                dashes=[2, 2])

    header = (f"{_INTERNAL_MARK} - {result['sheet']} - old p"
              f"{result['old_page'] + 1} vs new p"
              f"{result['new_page'] + 1}")
    if result["mode"] == MODE_PIXEL_ONLY:
        header += " - PIXEL ONLY (scanned input)"
    mark = page.add_freetext_annot(
        fitz.Rect(8, 8, 560, 24), header, fontsize=8, text_color=RED)
    mark.update()
    return drawn


# -- output B: takeoff_delta.md ---------------------------------------------

def _fmt_bbox(bbox) -> str:
    return "(" + ", ".join(f"{v:.1f}" for v in bbox) + ")"


def _code(text: str) -> str:
    return "`" + " ".join(str(text).split()) + "`"


def _sheet_section(res) -> list:
    lines = [
        "",
        f"## Sheet {res['sheet']} (old page {res['old_page'] + 1}, "
        f"new page {res['new_page'] + 1})",
        "",
    ]
    pixel = res["pixel"]
    if res["mode"] == MODE_PIXEL_ONLY:
        lines.append("Mode: PIXEL ONLY. " + " ".join(
            r.capitalize() + "." for r in res["pixel_only_reasons"]))
        lines.append("The text diff needs vector text on both issues, "
                     "so no member callout delta is available for "
                     "this sheet. Work the red boxes in the _DIFF "
                     "overlay by eye and re-take affected members "
                     "manually. All regions are low confidence.")
    else:
        lines.append("Mode: vector + pixel.")

    shift = pixel["shift_pt"]
    lines += [
        "",
        f"Pixel pass: {len(pixel['regions'])} changed regions after "
        f"merging, changed fraction "
        f"{pixel['changed_fraction'] * 100:.2f} percent of the sheet, "
        f"alignment shift ({shift[0]}, {shift[1]}) pt, phase "
        f"correlation response {pixel['response']}.",
    ]
    if pixel["shift_rejected"]:
        lines.append("WARNING: the estimated alignment shift exceeded "
                     f"{MAX_SHIFT_FRACTION:.0%} of the page and was "
                     "rejected; the diff ran unaligned and may "
                     "over-flag. Check the two inputs are the same "
                     "sheet.")
    if pixel["resized"]:
        lines.append("NOTE: the two renders differed in size; the old "
                     "issue was resampled to match. Treat region "
                     "edges with care.")
    if pixel["rotation_mismatch"]:
        lines.append("WARNING: the two pages carry different /Rotate "
                     "values, so the renders are oriented differently "
                     "and the pixel diff over-flags. Check the inputs "
                     "are the same sheet issued the same way.")
    for label, n in (("smallest raw regions ignored before merging",
                      pixel["dropped_small_premerge"]),
                     (f"smallest merged regions over the "
                      f"{MAX_REGIONS_PER_SHEET} cap not drawn",
                      pixel["dropped_over_cap"])):
        if n:
            lines.append(f"NOTE: {n} {label}.")
    if pixel["regions"]:
        lines.append("Largest changed regions (new-issue page "
                     "points):")
        for rect, area in list(zip(pixel["regions"],
                                   pixel["areas"]))[:10]:
            lines.append(f"- {_fmt_bbox(rect)} area {area:.0f} sq pt")
        if len(pixel["regions"]) > 10:
            lines.append(f"- and {len(pixel['regions']) - 10} more "
                         "(all boxed in the _DIFF overlay)")

    delta = res["callout_delta"]
    if delta is not None:
        lines += ["", "### Member callout delta (census grammar, "
                      "plan text, confidence medium)", ""]
        if delta:
            lines += [
                "| Designation | Class | Old | New | Delta | Where "
                "(page points) |",
                "|---|---|---:|---:|---:|---|",
            ]
            for r in delta:
                lines.append(
                    f"| {_code(r['designation'])} | {r['item_class']} "
                    f"| {r['old_count']} | {r['new_count']} | "
                    f"{r['delta']:+d} | {r['where_issue']} issue "
                    f"sample {_fmt_bbox(r['where_bbox'])} |")
            lines += ["",
                      "Counts are full-page census-grammar sweeps of "
                      "each issue, not takeoff quantities. Schedule "
                      "table changes appear here as text changes; the "
                      "census re-run below is the count of record."]
        else:
            lines.append("No member callout changes detected by the "
                         "text pass.")

    vec = res["vector"]
    if vec:
        if vec["changed"]:
            lines += ["", "### Changed text at matching locations", ""]
            total = len(vec["changed"])
            for item in vec["changed"][:80]:
                lines.append(
                    f"- {_code(item['old_text'])} to "
                    f"{_code(item['new_text'])} at "
                    f"{_fmt_bbox(item['new_bbox'])}")
            if total > 80:
                lines.append(
                    f"- and {total - 80} more changed words (first "
                    f"{min(total, MAX_CHANGED_ANNOTS)} boxed in the "
                    "overlay)")
            if total > MAX_CHANGED_ANNOTS:
                lines.append(
                    f"NOTE: {total - MAX_CHANGED_ANNOTS} changed-text "
                    f"boxes over the {MAX_CHANGED_ANNOTS} cap were "
                    "not drawn in the overlay; this sheet changed too "
                    "much to spot-check. Re-take it whole and re-run "
                    "the census.")
        desig_added = [i for i in vec["added"]
                       if _designations_in(i["text"])]
        desig_removed = [i for i in vec["removed"]
                         if _designations_in(i["text"])]
        if desig_added or desig_removed or vec["moved_designations"]:
            lines += ["", "### Added, removed, and relocated callouts",
                      ""]
            for item in desig_added[:80]:
                lines.append(f"- added {_code(item['text'])} at "
                             f"{_fmt_bbox(item['bbox'])}")
            for item in desig_removed[:80]:
                lines.append(f"- removed {_code(item['text'])} from "
                             f"{_fmt_bbox(item['bbox'])} (old issue)")
            for item in vec["moved_designations"][:80]:
                lines.append(f"- relocated {_code(item['text'])} to "
                             f"{_fmt_bbox(item['new_bbox'])}")
            for label, n in (("added", len(desig_added) - 80),
                             ("removed", len(desig_removed) - 80),
                             ("relocated",
                              len(vec["moved_designations"]) - 80)):
                if n > 0:
                    lines.append(f"- and {n} more {label} callouts "
                                 "(see the overlay popups)")
        lines += [
            "",
            f"Word totals: {len(vec['added'])} added, "
            f"{len(vec['removed'])} removed, {len(vec['changed'])} "
            f"changed, {vec['moved_count']} relocated. Median text "
            f"displacement ({vec['median_shift_pt'][0]}, "
            f"{vec['median_shift_pt'][1]}) pt.",
        ]
        if vec["pair_overflow"]:
            lines.append("NOTE: too many leftover words to pair "
                         "changed text; everything is listed as "
                         "added or removed for this sheet.")
    return lines


def _write_report(path, old_pdf, new_pdf, out_pdf, results,
                  pairing) -> None:
    lines = [
        "# Takeoff delta report (T10 revision diff)",
        "",
        "INTERNAL WORKING DOCUMENT. Never send to a client.",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "Module: takeoff_pipeline/revision_diff.py",
        f"Old issue: {old_pdf}",
        f"New issue: {new_pdf}",
        f"Overlay: {Path(out_pdf).name} (red boxes on changed "
        "regions, new-issue pages)",
        "",
        "Sheets diffed: " + ", ".join(r["sheet"] for r in results),
    ]
    for label, key in (("Sheets only in the old issue", "old_only"),
                       ("Sheets only in the new issue", "new_only"),
                       ("Ambiguous sheet numbers (skipped, pair "
                        "explicitly)", "ambiguous")):
        if pairing.get(key):
            lines.append(f"{label}: " + ", ".join(pairing[key]))

    for res in results:
        lines.extend(_sheet_section(res))

    lines += [
        "",
        "## Re-hash checklist (after human verification)",
        "",
        "1. Re-run the member census for this job against the new "
        "issue (takeoff_pipeline/census.py, run_census).",
        "2. Update the takeoff xlsx rows this delta touches, then "
        "re-export (takeoff_pipeline/export_xlsx.py).",
        "3. Re-stamp and verify the TAKEOFF hash "
        "(takeoff_pipeline/takeoff_hash.py, recipe per "
        "TAKEOFF_SCHEMA_V2.md 13.2; check with "
        "py -m takeoff_pipeline.validate_takeoff <takeoff.xlsx>).",
        "",
        "The delta above is evidence for the re-take, not a count of "
        "record (verify, do not generate).",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# -- driver -----------------------------------------------------------------

def _backup_outputs(paths) -> str:
    """Snapshot existing outputs before overwrite per the repo
    operating rule (the _DIFF overlay may carry markup). One snapshot
    dir per run plus a changelog line. Returns the dir or ''."""
    import shutil

    existing = [Path(p) for p in paths if Path(p).exists()]
    if not existing:
        return ""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    backup_dir = HANDOFF_ROOT / "backups" / ts
    # Two runs inside one second would land in the same dir and the
    # second would overwrite the first snapshot; uniquify instead.
    n = 1
    while backup_dir.exists():
        n += 1
        backup_dir = HANDOFF_ROOT / "backups" / f"{ts}-{n}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for p in existing:
        shutil.copy2(str(p), str(backup_dir / p.name))
    changelog = HANDOFF_ROOT / "changelog.md"
    with open(changelog, "a", encoding="utf-8") as f:
        f.write(f"\n{ts} - revision diff regenerate: "
                + ", ".join(p.name for p in existing)
                + f" backed up to _handoff/backups/{backup_dir.name}/"
                " before overwrite.")
    return str(backup_dir)


def run_revision_diff(old_pdf, new_pdf, pairs=None, sheets=None,
                      out_dir=None) -> dict:
    """Diff two issues of a drawing set.

    pairs: explicit [(old_index, new_index), ...] 0-based page
    indexes (a third tuple item names the sheet). Without it, pages
    auto-pair by sheet number; sheets filters the auto pairs by
    label. Outputs land in out_dir (default: beside the new issue):
    <new>_DIFF.pdf and takeoff_delta.md."""
    import fitz

    old_pdf = Path(old_pdf)
    new_pdf = Path(new_pdf)
    for p in (old_pdf, new_pdf):
        if not p.exists():
            raise FileNotFoundError(f"input not found: {p}")
    if new_pdf.stem.endswith("_DIFF"):
        raise ValueError(
            "the new issue input is already a _DIFF overlay; run "
            "against the issued sheet or boxes double up")
    if old_pdf.stem.endswith("_DIFF"):
        raise ValueError(
            "the old issue input is a _DIFF overlay; its red boxes "
            "would read as drawing changes. Diff the issued sheets.")

    pairing = {"old_only": [], "new_only": [], "ambiguous": []}
    if pairs is None:
        if old_pdf.resolve() == new_pdf.resolve():
            raise ValueError(
                "old and new are the same file; auto-pairing would "
                "diff every page against itself. Give --pairs "
                "explicitly (1-based OLD:NEW page numbers).")
        pairing = pair_sheets(old_pdf, new_pdf)
        pairs = [(p["old_page"], p["new_page"], p["sheet"])
                 for p in pairing["pairs"]]
        if sheets:
            wanted = {s.strip().upper() for s in sheets if s.strip()}
            pairs = [p for p in pairs if p[2].upper() in wanted]
            missing = wanted - {p[2].upper() for p in pairs}
            if missing:
                raise ValueError(
                    "requested sheets did not pair: "
                    + ", ".join(sorted(missing))
                    + ". Pairable sheets: "
                    + (", ".join(x["sheet"]
                                 for x in pairing["pairs"]) or "none"))
        if not pairs:
            raise ValueError(
                "no sheets could be paired between the two issues "
                "(no readable matching sheet numbers); give --pairs "
                "explicitly (1-based OLD:NEW page numbers)")
    else:
        pairs = [(int(p[0]), int(p[1]),
                  str(p[2]) if len(p) > 2 and p[2] else "")
                 for p in pairs]
    seen_new = {}
    for o, n, _label in pairs:
        if n in seen_new:
            raise ValueError(
                f"new page {n + 1} appears in more than one pair "
                f"(with old pages {seen_new[n] + 1} and {o + 1}); "
                "its boxes would double up. Run separate diffs.")
        seen_new[n] = o

    out_dir = Path(out_dir) if out_dir else new_pdf.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / f"{new_pdf.stem}_DIFF.pdf"
    report_path = out_dir / "takeoff_delta.md"
    if out_pdf.exists() and out_pdf.resolve() == old_pdf.resolve():
        raise ValueError(
            f"output {out_pdf.name} would overwrite the old issue "
            "input; use --out-dir")
    backed_up = _backup_outputs([out_pdf, report_path])

    results = []
    old_doc = fitz.open(str(old_pdf))
    new_doc = fitz.open(str(new_pdf))
    try:
        for o, n, label in pairs:
            if not 0 <= o < len(old_doc):
                raise ValueError(f"old page {o + 1} out of range "
                                 f"(1..{len(old_doc)})")
            if not 0 <= n < len(new_doc):
                raise ValueError(f"new page {n + 1} out of range "
                                 f"(1..{len(new_doc)})")
            sid = label or _sheet_id(new_doc[n]) or f"PAGE-{n + 1}"
            log.info("diffing sheet %s: old p%d vs new p%d", sid,
                     o + 1, n + 1)
            results.append(diff_pair(old_doc, o, new_doc, n, sid))
        for res in results:
            res["drawn"] = _annotate_page(new_doc[res["new_page"]],
                                          res)
        new_doc.save(str(out_pdf), garbage=3, deflate=True)
    finally:
        old_doc.close()
        new_doc.close()

    _write_report(report_path, old_pdf, new_pdf, out_pdf, results,
                  pairing)

    return {
        "out_pdf": str(out_pdf),
        "report": str(report_path),
        "pairs_diffed": len(results),
        "sheets": [{
            "sheet": r["sheet"],
            "mode": r["mode"],
            "pixel_regions": len(r["pixel"]["regions"]),
            "callout_delta_rows": (len(r["callout_delta"])
                                   if r["callout_delta"] is not None
                                   else None),
            "annotations": r["drawn"],
        } for r in results],
        "old_only": pairing["old_only"],
        "new_only": pairing["new_only"],
        "ambiguous": pairing["ambiguous"],
        "previous_backed_up": backed_up,
    }


def main() -> int:
    usage = (
        "usage: py -m takeoff_pipeline.revision_diff <old_pdf> "
        "<new_pdf>\n"
        "       [--pairs OLD:NEW[,OLD:NEW...]] "
        "[--sheets S-501,S-502] [--out-dir <dir>]\n"
        "page numbers in --pairs are 1-based; without --pairs, "
        "sheets auto-pair by sheet number")
    args = sys.argv[1:]
    if len(args) < 2 or args[0].startswith("--") \
            or args[1].startswith("--"):
        print(usage)
        return 2

    consumed = {0, 1}

    def flag(name):
        hits = [i for i, a in enumerate(args) if a == name]
        if not hits:
            return None
        if len(hits) > 1:
            raise ValueError(f"{name} given more than once")
        i = hits[0]
        if i + 1 >= len(args):
            raise ValueError(f"{name} needs a value")
        consumed.update((i, i + 1))
        return args[i + 1]

    try:
        pairs = None
        raw = flag("--pairs")
        if raw:
            pairs = []
            for part in raw.split(","):
                o, sep, n = part.partition(":")
                if not sep or not o.strip().isdigit() \
                        or not n.strip().isdigit():
                    raise ValueError(
                        f"bad --pairs entry '{part}'; expected "
                        "OLD:NEW 1-based page numbers")
                if int(o) < 1 or int(n) < 1:
                    raise ValueError("--pairs page numbers are "
                                     "1-based")
                pairs.append((int(o) - 1, int(n) - 1))
        raw = flag("--sheets")
        sheets = raw.split(",") if raw else None
        out_dir = flag("--out-dir")
        # A typo'd flag must not silently drop requested work.
        leftover = [args[i] for i in range(len(args))
                    if i not in consumed]
        if leftover:
            raise ValueError("unrecognized arguments: "
                             + " ".join(leftover))
        info = run_revision_diff(args[0], args[1], pairs=pairs,
                                 sheets=sheets, out_dir=out_dir)
    except (ValueError, FileNotFoundError) as e:
        print(e)
        print(usage)
        return 1
    print(f"overlay: {info['out_pdf']}")
    print(f"report:  {info['report']}")
    for s in info["sheets"]:
        delta = s["callout_delta_rows"]
        print(f"  {s['sheet']}: mode {s['mode']}, "
              f"{s['pixel_regions']} changed regions, "
              + ("callout delta rows "
                 f"{delta}" if delta is not None
                 else "no callout delta (pixel only)"))
    for key in ("old_only", "new_only", "ambiguous"):
        if info[key]:
            print(f"  {key}: {', '.join(info[key])}")
    if info["previous_backed_up"]:
        print(f"  previous outputs backed up: "
              f"{info['previous_backed_up']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
