"""
YourCo Virtual Office - R4 Self-Healer Human-Merge Gate
==========================================================

The Hermes self-healer (bridge/self_build.py, bridge/self_repair.py) previously
followed a write-evaluate-auto-commit pattern. R4 in HANDOFF changes that to
write-evaluate-propose: any generated skill or fix that touches the sensitive
surface lands in a quarantine directory and cannot load until a human merges it.

Sensitive surface (auto-detected):
- Imports of: bridge.aisc_validator, bridge.bid_rates, bridge.calculators,
  bridge.connection_engine, bridge.connection_weight
- File paths matching: takeoff*, *bid_rates*, *calculator*, *connection*,
  *shape*, *aisc*

Anything in this surface MUST go through human review. Defense in depth:
even after a human merges a proposed skill, the runtime path still routes
shapes through the validator and weight through the calculator. A bad merge
cannot inject an off-master shape or a hand-computed number.

Quarantine directory: skills/_proposed/
Active skills directory: skills/
(.claude/skills is a symlink that has been observed broken on some checkouts;
quarantine lives under skills/ at the repo root to avoid that breakage.)

This module is callable from:
- bridge/self_build.py save_extension() - replaces the direct write
- .githooks/pre-commit - blocks commits to sensitive paths that lack a
  human-merge marker
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
QUARANTINE_DIR = _REPO_ROOT / "skills" / "_proposed"
ACTIVE_SKILLS_DIR = _REPO_ROOT / "skills"
EXTENSIONS_DIR = _REPO_ROOT / "extensions"
QUARANTINE_LOG = _REPO_ROOT / "data" / "self_build_gate.jsonl"
HUMAN_MERGE_MARKER = ".human_merged"   # touch-file dropped by reviewer

# Sensitive imports (substring match, case-insensitive)
_SENSITIVE_IMPORTS = (
    "bridge.aisc_validator",
    "bridge.bid_rates",
    "bridge.calculators",
    "bridge.connection_engine",
    "bridge.connection_weight",
    "from bridge import aisc_validator",
    "from bridge import bid_rates",
    "from bridge import calculators",
    "from bridge import connection_engine",
    "from bridge import connection_weight",
)

# Sensitive path patterns (regex against relative path, case-insensitive)
_SENSITIVE_PATH_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"takeoff",
    r"bid_rates",
    r"calculator",
    r"connection",
    r"\bshape\b",
    r"aisc",
))


@dataclass
class GateDecision:
    sensitive: bool
    reasons: list[str] = field(default_factory=list)
    target_dir: Path = ACTIVE_SKILLS_DIR
    requires_human_merge: bool = False


def classify(rel_path: str, source_code: str) -> GateDecision:
    """Decide whether a proposed file is sensitive and where it should land."""
    reasons: list[str] = []

    # Path pattern check
    for pat in _SENSITIVE_PATH_PATTERNS:
        if pat.search(rel_path):
            reasons.append(f"path matches sensitive pattern /{pat.pattern}/")
            break

    # Import scan
    low = (source_code or "").lower()
    for needle in _SENSITIVE_IMPORTS:
        if needle.lower() in low:
            reasons.append(f"imports sensitive module '{needle}'")

    sensitive = bool(reasons)
    return GateDecision(
        sensitive=sensitive,
        reasons=reasons,
        target_dir=QUARANTINE_DIR if sensitive else ACTIVE_SKILLS_DIR,
        requires_human_merge=sensitive,
    )


def _ensure_quarantine() -> None:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    keep = QUARANTINE_DIR / ".gitkeep"
    if not keep.exists():
        keep.write_text(
            "# R4 self-healer quarantine. Files here must be human-merged "
            "before they will load.\n"
        )


def _log_decision(entry: dict) -> None:
    try:
        QUARANTINE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(QUARANTINE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log.warning("self_build_gate: failed to write log entry: %s", e)


def propose_skill(skill_name: str, source_code: str,
                  description: str = "") -> dict:
    """Replacement for the auto-commit path. Always quarantines anything
    that touches the sensitive surface. Returns a dict describing where the
    file landed and whether a human merge is required.
    """
    _ensure_quarantine()

    # Use the would-be skill path for classification
    rel_path = f"skills/{skill_name}/SKILL.py"
    decision = classify(rel_path, source_code)

    target_dir = decision.target_dir / skill_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "SKILL.py"
    header = (
        f'"""\nAuto-proposed by self-healer at '
        f'{datetime.now(timezone.utc).isoformat()}\n'
        f'Description: {description}\n'
        f'Sensitive: {decision.sensitive}\n'
        f'Reasons: {"; ".join(decision.reasons) if decision.reasons else "none"}\n'
        f'"""\n\n'
    )
    target_file.write_text(header + source_code + "\n", encoding="utf-8")

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": skill_name,
        "target": str(target_file.relative_to(_REPO_ROOT)),
        "sensitive": decision.sensitive,
        "reasons": decision.reasons,
        "requires_human_merge": decision.requires_human_merge,
        "description": description,
    }
    _log_decision(entry)

    return {
        "ok": True,
        "path": str(target_file),
        "sensitive": decision.sensitive,
        "reasons": decision.reasons,
        "requires_human_merge": decision.requires_human_merge,
        "human_merge_marker": str(target_dir / HUMAN_MERGE_MARKER),
    }


def is_quarantined(skill_dir: Path) -> bool:
    """True iff the skill dir is in the quarantine area."""
    try:
        skill_dir.resolve().relative_to(QUARANTINE_DIR.resolve())
        return True
    except ValueError:
        return False


def is_merged(skill_dir: Path) -> bool:
    """A quarantined skill is loadable only after a reviewer drops the marker."""
    return (skill_dir / HUMAN_MERGE_MARKER).exists()


def is_loadable(skill_dir: Path) -> bool:
    """Loader gate. Active-dir skills are always loadable. Quarantined skills
    must have the human-merge marker present.
    """
    if not is_quarantined(skill_dir):
        return True
    return is_merged(skill_dir)


# ---------------------------------------------------------------
# Pre-commit hook helper
# ---------------------------------------------------------------

def staged_files() -> list[str]:
    """Files staged for commit (relative to repo root)."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(_REPO_ROOT), text=True, timeout=10
        )
        return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception as e:
        log.warning("self_build_gate: git diff failed: %s", e)
        return []


def precommit_check() -> tuple[bool, list[str]]:
    """Return (ok, messages). Block when any staged file is sensitive and is
    landing outside the quarantine without a human-merge marker.
    """
    msgs: list[str] = []
    files = staged_files()
    ok = True

    for rel in files:
        # Skip deletes (file no longer present)
        path = _REPO_ROOT / rel
        if not path.exists():
            continue
        # Only scan .py files; the gate is about executable code
        if not rel.endswith(".py"):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        decision = classify(rel, source)
        if not decision.sensitive:
            continue

        # If it lives under skills/_proposed/, allow only if reviewer
        # dropped the human-merge marker in the same skill dir.
        rel_path = Path(rel)
        if "skills/_proposed/" in rel.replace("\\", "/"):
            marker = path.parent / HUMAN_MERGE_MARKER
            if marker.exists():
                msgs.append(f"OK quarantine-merged: {rel}")
                continue
            msgs.append(f"BLOCK {rel}: in quarantine without human-merge marker")
            ok = False
            continue

        # Sensitive file landing outside quarantine: require marker beside it.
        marker_candidates = [path.parent / HUMAN_MERGE_MARKER]
        if any(m.exists() for m in marker_candidates):
            msgs.append(f"OK reviewed: {rel}")
            continue

        msgs.append(
            f"BLOCK {rel}: sensitive surface ({'; '.join(decision.reasons)}). "
            f"Move to skills/_proposed/ or add {HUMAN_MERGE_MARKER} marker."
        )
        ok = False

    return ok, msgs


# CLI for the pre-commit hook
def _main_precommit() -> int:
    ok, msgs = precommit_check()
    for m in msgs:
        print(m)
    if not ok:
        print("")
        print("R4 GATE: blocking commit. Resolve the above before re-trying.")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main_precommit())
