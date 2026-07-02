"""F20: Multi-provider consensus merge.

Run two or three vision providers on the same page image, then merge.
The intuition: when Gemini Flash AND Opus AND/or GPT-4o all see the
same shape at roughly the same bbox, that detection is HIGH confidence.
When only one model sees it, it's lower confidence and the cluster
gets flagged as "uncertain".

Adapted from the LIFT/Sketchdeck adaptive-confidence pattern and from
internal estimator review experience: human reviewers automatically
flag low-agreement zones first.

Pipeline:
    detections_gem = vision_detect._call_gemini(img)
    detections_ant = vision_detect._call_anthropic(img)
    detections_oai = vision_detect._call_openai(img)

    merged = merge_consensus(
        [detections_gem, detections_ant, detections_oai],
        provider_names=["gemini", "anthropic", "openai"],
        iou_threshold=0.4,
    )

Each merged entry carries:
    providers: ["gemini", "anthropic"]  # who agreed
    agreement: 2  # number of providers that voted
    consensus_confidence: 0.0 - 1.0

This is the most expensive layer because it calls 3 models per page.
auto_bid.py exposes consensus=False by default and consensus=True
under --high-accuracy.
"""

from __future__ import annotations
from .detection_dedup import _iou, _norm_shape


def merge_consensus(provider_results: list[list[dict]],
                    provider_names: list[str],
                    iou_threshold: float = 0.4) -> list[dict]:
    """Cluster detections across providers and emit one entry per cluster.

    A cluster is built greedily: pick any unclaimed detection, find all
    detections from OTHER providers with same normalized shape and
    IoU >= threshold (or matching mark). Stamp the cluster with the
    list of providers that contributed.
    """
    # Flatten with provider tag
    flat: list[tuple[str, dict]] = []
    for provider, dets in zip(provider_names, provider_results):
        for d in dets:
            flat.append((provider, d))

    used = [False] * len(flat)
    out: list[dict] = []

    for i, (pi, di) in enumerate(flat):
        if used[i]:
            continue
        cluster_members = [(pi, di)]
        used[i] = True

        for j in range(i + 1, len(flat)):
            if used[j]:
                continue
            pj, dj = flat[j]
            if pj == pi:
                continue  # need cross-provider agreement
            if _norm_shape(di.get("shape")) != _norm_shape(dj.get("shape")):
                continue
            if (di.get("page") is not None and dj.get("page") is not None
                    and di.get("page") != dj.get("page")):
                continue
            mark_i = (di.get("mark") or "").strip().upper()
            mark_j = (dj.get("mark") or "").strip().upper()
            if mark_i and mark_i == mark_j:
                cluster_members.append((pj, dj))
                used[j] = True
                continue
            if _iou(di.get("bbox") or [], dj.get("bbox") or []) >= iou_threshold:
                cluster_members.append((pj, dj))
                used[j] = True

        # Pick representative: prefer highest confidence
        cluster_members.sort(
            key=lambda pd: float(pd[1].get("confidence") or 0.0), reverse=True)
        rep = dict(cluster_members[0][1])

        providers = sorted({p for p, _ in cluster_members})
        confs = [float(d.get("confidence") or 0.0) for _, d in cluster_members]
        agreement = len(providers)

        rep["providers"] = providers
        rep["agreement"] = agreement
        # Consensus confidence = mean conf scaled by agreement
        # 1 provider:  scale 1.0  -> low boost
        # 2 providers: scale 1.15
        # 3 providers: scale 1.30 (capped at 0.99)
        scale = 1.0 + 0.15 * (agreement - 1)
        boosted = min(0.99, (sum(confs) / max(1, len(confs))) * scale)
        rep["consensus_confidence"] = round(boosted, 3)
        rep["raw_member_count"] = len(cluster_members)
        # Also keep the rep's own conf
        if agreement >= 2:
            rep["confidence"] = max(float(rep.get("confidence") or 0.0), boosted)
            rep["status"] = "Consensus"
        out.append(rep)

    return out


def consensus_report(merged: list[dict]) -> dict:
    multi = [d for d in merged if d.get("agreement", 1) >= 2]
    single = [d for d in merged if d.get("agreement", 1) == 1]
    return {
        "total_clusters": len(merged),
        "multi_provider_clusters": len(multi),
        "single_provider_clusters": len(single),
        "multi_provider_pct": (
            round(len(multi) / len(merged), 3) if merged else 0.0
        ),
    }
