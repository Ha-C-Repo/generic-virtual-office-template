"""First-launch local-model setup orchestrator.

This module is invoked once at install time (or on demand from a Tools
menu) to:
    1. Scan hardware (delegated to hardware_detector.py)
    2. Pick the right Ollama model for the detected GPU/VRAM
    3. Pip-install the right DocTR variant (torch vs tf, CPU vs CUDA)
    4. Pip-install the Ollama Python client (small, optional)
    5. Pull the chosen Ollama model via the daemon

Each step is independent and reports its own success / failure. A
single step failing does not block the others. If everything fails,
the system still works in cloud-only mode (Tier 2 + Tier 3).

The function is also re-runnable. If a user later upgrades their GPU,
they can rerun this from the Tools menu and the system will detect the
new card and switch the model.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import subprocess
import sys
from pathlib import Path
from typing import Optional

# Module-level imports so tests can patch these symbols on this module.
from .ollama_client import is_ollama_running, pull_model_if_missing


def install_local_dependencies(profile: dict,
                                pip_executable: Optional[str] = None,
                                dry_run: bool = False) -> dict:
    """Pip-install DocTR + ollama Python client based on hardware profile.

    Args:
        profile: dict produced by hardware_detector.write_hardware_profile().
        pip_executable: full path to pip (default: same interpreter's pip).
        dry_run: if True, return the command list without executing.

    Returns:
        dict with keys:
            doctr_install: {"success": bool, "command": str, "output": str}
            ollama_client_install: {"success": bool, "command": str, "output": str}
    """
    pip = pip_executable or _default_pip()
    has_gpu = bool(profile.get("gpu", {}).get("has_gpu"))
    vendor = profile.get("gpu", {}).get("vendor", "unknown")

    # DocTR variant: torch + CUDA when NVIDIA, plain torch on CPU,
    # tf path is offered as a fallback for users without torch.
    if has_gpu and vendor == "NVIDIA":
        doctr_pkg = "python-doctr[torch]"
    else:
        doctr_pkg = "python-doctr[torch]"  # torch CPU build still works

    doctr_cmd = [pip, "install", "--upgrade", doctr_pkg]
    ollama_cmd = [pip, "install", "--upgrade", "ollama"]

    if dry_run:
        return {
            "doctr_install": {
                "success": True,
                "command": " ".join(doctr_cmd),
                "output": "(dry run)",
            },
            "ollama_client_install": {
                "success": True,
                "command": " ".join(ollama_cmd),
                "output": "(dry run)",
            },
        }

    return {
        "doctr_install": _run_subprocess(doctr_cmd),
        "ollama_client_install": _run_subprocess(ollama_cmd),
    }


def run_first_launch_setup(profile_path: Optional[Path] = None,
                            skip_pip: bool = False,
                            skip_pull: bool = False,
                            dry_run: bool = False) -> dict:
    """Full first-launch ritual.

    Returns a dict with one entry per step so the caller (installer
    NSIS post-install action OR Tools menu refresh button) can show
    a checklist UI to the user.
    """
    from .hardware_detector import write_hardware_profile, PROFILE_PATH

    target_path = profile_path or PROFILE_PATH

    report = {
        "hardware_scan": {"success": False, "data": None, "error": ""},
        "pip_install": {"success": False, "data": None, "error": ""},
        "ollama_running": {"success": False, "data": None, "error": ""},
        "model_pull": {"success": False, "data": None, "error": ""},
        "summary": "",
    }

    # 1. Hardware scan + profile write
    try:
        profile = write_hardware_profile(target_path)
        report["hardware_scan"] = {
            "success": True,
            "data": profile,
            "error": "",
        }
    except Exception as e:
        report["hardware_scan"] = {
            "success": False,
            "data": None,
            "error": str(e),
        }
        report["summary"] = "Hardware scan failed. Cannot proceed."
        return report

    # 2. Pip install (optional, can be skipped for fast smoke tests)
    if skip_pip:
        report["pip_install"] = {
            "success": True,
            "data": {"skipped": True},
            "error": "",
        }
    else:
        pip_result = install_local_dependencies(profile, dry_run=dry_run)
        all_ok = (pip_result["doctr_install"]["success"] and
                  pip_result["ollama_client_install"]["success"])
        report["pip_install"] = {
            "success": all_ok,
            "data": pip_result,
            "error": "" if all_ok else "One or more pip installs failed",
        }

    # 3. Ollama daemon check
    daemon_up = is_ollama_running()
    report["ollama_running"] = {
        "success": daemon_up,
        "data": {"daemon_running": daemon_up},
        "error": "" if daemon_up else (
            "Ollama daemon is not running. "
            "Install Ollama from ollama.com and start the service."
        ),
    }

    # 4. Pull recommended model if daemon is up and we have one
    rec = profile.get("ollama_recommendation", {}) or {}
    chosen = rec.get("model")
    if not chosen:
        report["model_pull"] = {
            "success": True,
            "data": {"skipped": True,
                     "reason": "No local vision model recommended for this hardware"},
            "error": "",
        }
    elif not daemon_up:
        report["model_pull"] = {
            "success": False,
            "data": {"model": chosen, "skipped": True},
            "error": "Ollama daemon down. Skipping model pull.",
        }
    elif skip_pull or dry_run:
        report["model_pull"] = {
            "success": True,
            "data": {"model": chosen, "skipped": True,
                     "reason": "skip_pull or dry_run"},
            "error": "",
        }
    else:
        pull_res = pull_model_if_missing(chosen)
        report["model_pull"] = {
            "success": pull_res.get("success", False),
            "data": pull_res,
            "error": pull_res.get("message", "") if not pull_res.get("success") else "",
        }

    # Build human summary line
    parts = []
    if report["hardware_scan"]["success"]:
        gpu = profile.get("gpu", {})
        if gpu.get("has_gpu"):
            parts.append(f"GPU: {gpu.get('model','?')} ({gpu.get('vram_gb',0):.1f}GB)")
        else:
            parts.append("GPU: none detected")
    if chosen:
        parts.append(f"Model: {chosen}")
    else:
        parts.append("Model: cloud-only fallback")
    if daemon_up:
        parts.append("Ollama: running")
    else:
        parts.append("Ollama: not running")
    report["summary"] = ". ".join(parts) + "."

    return report


# ── Helpers ────────────────────────────────────────────────────────────────

def _default_pip() -> str:
    """Return the pip executable path tied to the current interpreter."""
    return f"{sys.executable}"


def _run_subprocess(cmd: list[str]) -> dict:
    """Run a subprocess command. Returns success / output dict."""
    # If we were handed `python` (because _default_pip just returned
    # sys.executable), promote to "python -m pip".
    if cmd and cmd[0] == sys.executable and "pip" not in cmd[0]:
        cmd = [sys.executable, "-m", "pip"] + cmd[1:]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return {
            "success": result.returncode == 0,
            "command": " ".join(cmd),
            "output": (result.stdout or "") + (result.stderr or ""),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "command": " ".join(cmd),
            "output": "Timeout after 600 seconds",
        }
    except (OSError, subprocess.SubprocessError) as e:
        return {
            "success": False,
            "command": " ".join(cmd),
            "output": str(e),
        }
