"""F03: Drawing-stage diff (Rev N vs Rev N-1).

When a Rev 1 set replaces IFB or Rev 0, compare the two BOQs and
report what changed. Tonnage delta, members added/removed/changed
length, shape changes.

Refactored from cowork_bid/drawing_diff.py (2026-05-27 cherry-pick) to
use canonical bridge/aisc_validator.py for shape weights. The caller
loads member lists from whatever boq source they prefer (canonical
has boq_resolver / boq_sources / boq_discovery). Member-list-in,
diff-out keeps this module standalone and testable.

Source: Joseph Hasse, 2026-05-27, cherry-pick from
C:\\Users\\YourUser\\Projects\\Cowork Virtual Office\\cowork_bid\\
README: _handoff/proposed-patches/2026-05-27T16-38-47Z-cowork_bid-cherrypick/README.md
"""

from __future__ import annotations
from bridge.aisc_validator import validate_shape


def _key(m: dict) -> tuple:
    """Identity tuple for matching members across revs.

    shape + mark + length is enough to catch identity through rev changes.
    Two members with same shape and mark but different length = changed.
    """
    return (
        (m.get("shape") or "").upper().strip(),
        (m.get("mark") or m.get("piece_mark") or "").upper().strip(),
        round(float(m.get("length_ft", 0) or 0), 2),
    )


def _mark_key(m: dict) -> tuple:
    """Mark-only identity (shape + mark, no length). Used to detect
    members that changed length between revs vs members that are truly
    new or removed."""
    return (
        (m.get("shape") or "").upper().strip(),
        (m.get("mark") or m.get("piece_mark") or "").upper().strip(),
    )


def _tons(m: dict) -> float:
    """Compute member tonnage using canonical AISC validator."""
    v = validate_shape(m.get("shape", ""))
    qty = int(m.get("qty", 1) or 1)
    lft = float(m.get("length_ft", 0) or 0)
    if not v.get("valid"):
        return 0.0
    lb_per_ft = v.get("lb_per_ft") or v.get("weight_per_ft") or 0
    return (lb_per_ft * lft * qty) / 2000.0


def compare_members(old_members: list, new_members: list,
                    old_label: str = "old", new_label: str = "new") -> dict:
    """Compare two member lists. Returns a structured diff.

    Args:
        old_members: list of member dicts (older rev)
        new_members: list of member dicts (newer rev)
        old_label: label for old rev (e.g. "Rev 0" or "IFB")
        new_label: label for new rev (e.g. "Rev 1" or "IFC")

    Member dict keys recognized: shape, mark/piece_mark, length_ft, qty.
    Extras pass through to added/removed/changed output unchanged.

    Returns:
        dict with old/new counts, added, removed, length-changed,
        tonnage delta in tons and percent.
    """
    old_by_key = {_key(m): m for m in (old_members or [])}
    new_by_key = {_key(m): m for m in (new_members or [])}
    old_by_mark = {_mark_key(m): m for m in (old_members or [])}
    new_by_mark = {_mark_key(m): m for m in (new_members or [])}

    added_keys = [k for k in new_by_key if k not in old_by_key]
    removed_keys = [k for k in old_by_key if k not in new_by_key]

    # Among added / removed, find pairs that share shape+mark but
    # changed length. Those are "changed" not added/removed.
    added = []
    removed = []
    changed = []
    seen_marks = set()
    for k in added_keys:
        mk = (k[0], k[1])
        if mk in old_by_mark and mk in new_by_mark and mk not in seen_marks:
            old_m = old_by_mark[mk]
            new_m = new_by_mark[mk]
            old_len = round(float(old_m.get("length_ft", 0) or 0), 2)
            new_len = round(float(new_m.get("length_ft", 0) or 0), 2)
            if old_len != new_len:
                changed.append({
                    "shape": k[0], "mark": k[1],
                    "old_length_ft": old_len,
                    "new_length_ft": new_len,
                    "length_delta_ft": round(new_len - old_len, 2),
                })
                seen_marks.add(mk)
                continue
        added.append(new_by_key[k])
    for k in removed_keys:
        mk = (k[0], k[1])
        if mk in seen_marks:
            continue
        removed.append(old_by_key[k])

    unchanged_count = sum(1 for k in new_by_key if k in old_by_key)
    old_tons = sum(_tons(m) for m in (old_members or []))
    new_tons = sum(_tons(m) for m in (new_members or []))
    pct = ((new_tons - old_tons) / old_tons * 100) if old_tons else 0.0

    return {
        "old_label": old_label,
        "new_label": new_label,
        "old_member_count": len(old_members or []),
        "new_member_count": len(new_members or []),
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "unchanged_count": unchanged_count,
        "old_tons": round(old_tons, 2),
        "new_tons": round(new_tons, 2),
        "tonnage_delta_tons": round(new_tons - old_tons, 2),
        "tonnage_delta_pct": round(pct, 1),
        "added": added[:25],
        "removed": removed[:25],
        "changed": changed[:25],
    }


def compare_boqs_from_resolver(old_ctx, new_ctx):
    """Convenience wrapper for callers using canonical boq_resolver.

    old_ctx, new_ctx: BoqContext-shaped objects passed to
    bridge.boq_resolver.resolve_boq(). Each ResolutionResult should
    have a `members` field (or similar).
    """
    from bridge import boq_resolver
    old_result = boq_resolver.resolve_boq(old_ctx)
    new_result = boq_resolver.resolve_boq(new_ctx)
    old_members = getattr(old_result, "members", None) or []
    new_members = getattr(new_result, "members", None) or []
    return compare_members(old_members, new_members,
                           old_label=getattr(old_ctx, "label", "old"),
                           new_label=getattr(new_ctx, "label", "new"))


# Smoke test
if __name__ == "__main__":
    old = [
        {"shape": "W12X26", "mark": "B1", "length_ft": 30, "qty": 4},
        {"shape": "W14X22", "mark": "B2", "length_ft": 25, "qty": 6},
        {"shape": "HSS6X6X1/4", "mark": "C1", "length_ft": 14, "qty": 12},
    ]
    new = [
        {"shape": "W12X26", "mark": "B1", "length_ft": 32, "qty": 4},  # length changed
        {"shape": "W14X22", "mark": "B2", "length_ft": 25, "qty": 6},  # unchanged
        # C1 removed
        {"shape": "HSS8X8X3/8", "mark": "C2", "length_ft": 14, "qty": 16},  # added
    ]
    d = compare_members(old, new, "Rev 0", "Rev 1")
    for k, v in d.items():
        if k in ("added", "removed", "changed"):
            print(f"{k}: {len(v)} items")
            for it in v:
                print(f"  {it}")
        else:
            print(f"{k}: {v}")
