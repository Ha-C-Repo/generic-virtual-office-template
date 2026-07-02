"""
AI Model Router - Pass 8

Single source of truth for "which Claude model do I call for this task."
Adds tier-based routing so Joseph can swap models in one place when newer
versions ship, and Owner can escalate to Opus 4.7 for tasks where the
default Sonnet output isn't accurate enough.

DESIGN
──────
Four tiers, latest-generation models:

  T1 fast    -> claude-haiku-4-5-20251001  (chat, classification, summarize)
  T2 default -> claude-sonnet-4-6          (drafting, takeoff, voice, bids)
  T3 accurate-> claude-opus-4-6            (complex reasoning, code review)
  T4 max     -> claude-opus-4-7            (max accuracy, high-stakes)

Most workloads stay on T2 (Sonnet 4.6). T3/T4 are escalation tiers - used
when accuracy or UX benefits clearly outweigh cost. T1 is for chat-style
fast responses where a small model is sufficient.

The hard-coded MODEL_ROUTES dict in bridge/api.py is preserved as a fallback.
This router supplements it: if a task type has been escalated, the router
returns the higher-tier model. Otherwise, it returns the legacy default.

OVERRIDES
─────────
Persisted to data/model_routing.json so they survive restarts. Owner can
type `use opus for compliance` and it sticks until cleared.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
_OVERRIDES_FILE = _DATA / "model_routing.json"

# ─────────────────────────────────────────────────────────────────
# MODEL REGISTRY (latest-generation Claude models)
# ─────────────────────────────────────────────────────────────────

TIERS = {
    "fast": {
        "model": "claude-haiku-4-5-20251001",
        "label": "Haiku 4.5",
        "cost_tier": "lowest",
        "best_for": "chat replies, classification, summarization, simple lookups",
    },
    "default": {
        "model": "claude-sonnet-4-6",
        "label": "Sonnet 4.6",
        "cost_tier": "standard",
        "best_for": "drafting, takeoff, voice calibration, bid strategy, general reasoning",
    },
    "accurate": {
        "model": "claude-opus-4-6",
        "label": "Opus 4.6",
        "cost_tier": "high",
        "best_for": "complex compliance reasoning, code review, multi-step planning",
    },
    "max": {
        # BUG-009 FIX: claude-opus-4-7 does not exist yet. Any task escalated to
        # this tier was hitting an API "model_not_found" error. Redirected to Opus
        # 4.6 (T3/accurate) until Opus 4.7 ships. Update model string here when it
        # becomes available - no other changes needed (all T4 callers route through
        # get_model_for_task).
        "model": "claude-opus-4-6",
        "label": "Opus 4.6 (T4 placeholder - Opus 4.7 not yet available)",
        "cost_tier": "high",
        "best_for": "max-accuracy bid analysis, high-stakes vendor negotiations, "
                    "ambiguous compliance edge cases",
    },
}

# Default task-to-tier map. Override via set_tier_for_task() or
# `use opus for <task>` chat command.
DEFAULT_TASK_TIERS = {
    # Fast tier - chat-style, no deep reasoning
    "chat_shortcut":       "fast",
    "classify_intent":     "fast",
    "summarize_brief":     "fast",
    "extract_keyword":     "fast",

    # Default tier - the workhorse
    "voice_draft":         "default",
    "bid_strategy":        "default",
    "compliance":          "default",
    "cold_outreach":       "default",
    "general":             "default",
    "takeoff_extract":     "default",
    "icd_church":          "default",
    "afr_refinery":        "default",
    "model_3d":            "default",

    # Accurate tier - escalations where Opus 4.6 helps
    "code_review":         "accurate",
    "vj_design_feature":   "accurate",
    "complex_compliance":  "accurate",
    "bid_post_mortem":     "accurate",

    # Max tier - reserved, only when explicitly requested
    "high_stakes_bid":     "max",
    "vendor_negotiation":  "max",
}

# ─────────────────────────────────────────────────────────────────
# OVERRIDE STORAGE
# ─────────────────────────────────────────────────────────────────

def _load_overrides() -> dict:
    try:
        if _OVERRIDES_FILE.exists():
            return json.loads(_OVERRIDES_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_overrides(data: dict) -> None:
    # SIM/VJ-MUST-FIX-04: if there are no overrides, delete the file rather
    # than writing an empty {}. The loader handles missing-file just fine,
    # and an empty file gets flagged by VJ as empty_data_file bloat.
    if not data:
        try:
            if _OVERRIDES_FILE.exists():
                _OVERRIDES_FILE.unlink()
        except Exception:
            pass
        return
    _OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDES_FILE.write_text(json.dumps(data, indent=2, default=str))

# ─────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────

def pick_model(task_type: str = "general") -> str:
    """Return the model_id for a given task. Honors overrides."""
    overrides = _load_overrides()
    tier = overrides.get(task_type) or DEFAULT_TASK_TIERS.get(task_type, "default")
    if tier not in TIERS:
        tier = "default"
    return TIERS[tier]["model"]

def pick_tier(task_type: str = "general") -> str:
    """Return the tier name for a given task."""
    overrides = _load_overrides()
    return overrides.get(task_type) or DEFAULT_TASK_TIERS.get(task_type, "default")

def set_tier_for_task(task_type: str, tier: str) -> dict:
    """Override the tier for a task type. Persisted to disk."""
    # vj: parity-ok (pass 10g classified: dispatcher J=0.20; disjoint shapes)
    if tier not in TIERS:
        return {"ok": False, "error": f"unknown tier '{tier}'. valid: {list(TIERS)}"}
    overrides = _load_overrides()
    overrides[task_type] = tier
    _save_overrides(overrides)
    return {"ok": True, "task_type": task_type, "tier": tier,
            "model": TIERS[tier]["model"]}

def clear_override(task_type: str) -> dict:
    """Remove an override for a task type, reverting to default."""
    overrides = _load_overrides()
    if task_type in overrides:
        prev_tier = overrides.pop(task_type)
        _save_overrides(overrides)
        return {"ok": True, "task_type": task_type, "removed_tier": prev_tier,
                "now_default": DEFAULT_TASK_TIERS.get(task_type, "default")}
    return {"ok": True, "task_type": task_type, "note": "no override was set"}

def clear_all_overrides() -> dict:
    """Wipe all overrides. Useful for `reset model routing` chat command."""
    count = len(_load_overrides())
    _save_overrides({})
    return {"ok": True, "cleared": count}

def get_routing_map() -> dict:
    """Return the full current routing map: defaults + overrides + tier specs."""
    overrides = _load_overrides()
    tasks = {}
    seen = set()
    for task in sorted(set(list(DEFAULT_TASK_TIERS) + list(overrides))):
        tier = overrides.get(task) or DEFAULT_TASK_TIERS.get(task, "default")
        tasks[task] = {
            "tier": tier,
            "model": TIERS.get(tier, TIERS["default"])["model"],
            "overridden": task in overrides,
            "default_tier": DEFAULT_TASK_TIERS.get(task, "default"),
        }
        seen.add(task)
    return {
        "tiers":             TIERS,
        "tasks":             tasks,
        "active_overrides":  overrides,
        "total_tasks":       len(tasks),
        "overridden_count":  len(overrides),
        "generated_at":      datetime.now(timezone.utc).isoformat(),
    }

def get_model_for_escalation(target_tier: str = "max") -> str:
    """Return the model_id for an explicit escalation call (e.g. `use opus`)."""
    if target_tier not in TIERS:
        target_tier = "max"
    return TIERS[target_tier]["model"]

def list_models() -> list:
    """List all available models with metadata. For the Settings panel."""
    return [
        {"tier": t, **spec} for t, spec in TIERS.items()
    ]

# ─────────────────────────────────────────────────────────────────
# CLI for Joseph's debug
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        print(json.dumps(get_routing_map(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "models":
        print(json.dumps(list_models(), indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] == "set":
        print(json.dumps(set_tier_for_task(sys.argv[2], sys.argv[3]), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "clear-all":
        print(json.dumps(clear_all_overrides(), indent=2))
    else:
        print("Usage: python ai_model_router.py [show|models|set <task> <tier>|clear-all]")
