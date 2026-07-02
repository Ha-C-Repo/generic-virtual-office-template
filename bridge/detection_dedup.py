"""F16: Detection deduplication (spatial IoU + mark + shape).

Vision providers regularly return the same physical member multiple
times: the same HSS column appears in 4-12 overlapping bounding boxes
on a foundation plan because the model "sees" it on every pass over a
busy region. Without dedup, the BOQ counts inflate by 3-5x or the
member is rejected and the BOQ counts collapse to a fraction.

v14 Frutia: 101 raw detections collapsed to 25 unique members. That
75% duplication was the single largest accuracy drop.

This module:
1. Clusters detections by (page, shape_normalized) bucket
2. Within each bucket, runs IoU greedy merge (threshold 0.5)
3. Within each bucket, also merges by piece mark when printed
4. Keeps the highest-confidence representative per cluster
5. Sums length_ft and qty across the cluster (when both > 0)

Outputs the same dict shape as input, plus a "cluster_size" field
that tells the auto_review how many raw detections collapsed to this
one normalized member.

NEVER invent shape names. NEVER widen merge thresholds without a
calibration test against a hand-counted drawing.
"""

from __future__ import annotations
from typing import Iterable


DEFAULT_IOU_THRESHOLD = 0.5
SAME_BBOX_TOLERANCE_PX = 4.0  # bbox coords within 4 pixels = same detection


def _iou(a: list[float], b: list[float]) -> float:
    """Intersection-over-union for two [x0,y0,x1,y1] boxes."""
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0.0
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def _identical_bbox(a, b, tol=SAME_BBOX_TOLERANCE_PX):
    if not a or not b or len(a) != 4 or len(b) != 4:
        return False
    return all(abs(a[i] - b[i]) <= tol for i in range(4))


def _norm_shape(s):
    return (s or "").strip().upper().replace(" ", "")


def dedup_detections(detections: Iterable[dict],
                     iou_threshold: float = DEFAULT_IOU_THRESHOLD) -> list[dict]:
    """Cluster duplicate detections, return one representative per cluster.

    Cluster rule (any of the following collapses A and B together):
      - identical (shape, page, mark) AND non-empty mark
      - identical (shape, page) AND IoU(bbox_a, bbox_b) >= threshold
      - identical (shape, page) AND bbox_a == bbox_b within tolerance

    Representative selection: highest confidence. Length and qty
    are taken from the representative (NOT summed, because each
    cluster represents ONE physical member, not N).

    Returns clusters with added fields:
        cluster_size: int  # how many raw detections collapsed
        cluster_confidence: float  # mean confidence across cluster
    """
    dets = list(detections)
    used = [False] * len(dets)
    out: list[dict] = []

    # Pre-bucket by (page, shape) for speed
    buckets: dict[tuple, list[int]] = {}
    for i, d in enumerate(dets):
        key = (d.get("page"), _norm_shape(d.get("shape")))
        buckets.setdefault(key, []).append(i)

    for key, idxs in buckets.items():
        for i in idxs:
            if used[i]:
                continue
            cluster = [i]
            used[i] = True
            for j in idxs:
                if j == i or used[j]:
                    continue
                a, b = dets[i], dets[j]
                mark_a = (a.get("mark") or "").strip().upper()
                mark_b = (b.get("mark") or "").strip().upper()
                same_mark = bool(mark_a) and mark_a == mark_b

                if same_mark:
                    cluster.append(j)
                    used[j] = True
                    continue
                if _identical_bbox(a.get("bbox"), b.get("bbox")):
                    cluster.append(j)
                    used[j] = True
                    continue
                if _iou(a.get("bbox") or [], b.get("bbox") or []) >= iou_threshold:
                    cluster.append(j)
                    used[j] = True
                    continue

            # Build representative
            members = [dets[k] for k in cluster]
            members.sort(key=lambda m: float(m.get("confidence") or 0.0), reverse=True)
            rep = dict(members[0])  # shallow copy
            confs = [float(m.get("confidence") or 0.0) for m in members]
            rep["cluster_size"] = len(members)
            rep["cluster_confidence"] = round(sum(confs) / len(confs), 3) if confs else 0.0
            out.append(rep)

    return out


def dedup_report(before: list[dict], after: list[dict]) -> dict:
    """Quick diagnostic dict for auto_review."""
    return {
        "raw_count": len(before),
        "unique_count": len(after),
        "collapse_ratio": round(1 - len(after) / max(1, len(before)), 3),
        "max_cluster_size": max((d.get("cluster_size", 1) for d in after), default=0),
    }
