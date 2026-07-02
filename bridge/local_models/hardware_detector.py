"""Hardware detection for local model sizing.

Scans the host machine for GPU and VRAM, then recommends an Ollama
model that fits the available hardware. The detector runs at install
time and is re-runnable at any later point if the user upgrades their
GPU. Results are written to data/hardware_profile.json so the rest of
the system can read the chosen model without re-scanning every launch.

Detection order (cross-platform, no extra pip deps required):
    1. nvidia-smi  (NVIDIA, any OS, most reliable for VRAM)
    2. wmic        (Windows fallback, works without NVIDIA driver)
    3. system_profiler  (macOS Apple Silicon and discrete cards)
    4. lspci       (Linux fallback)

If none succeed, the detector reports "no GPU" and the system falls
back to Gemini-only Tier 2 with DocTR running CPU-only OCR.

VRAM-to-model mapping (llama3.2-vision and friends):
    >= 60 GB  -> llama3.2-vision:90b   (workstation cards: A100, H100)
    >= 6 GB   -> llama3.2-vision:11b   (consumer GPUs: RTX 3060+ )
    >= 4 GB   -> moondream:1.8b        (lightweight, 8 GB systems)
    < 4 GB    -> no local vision; DocTR only (CPU)

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Module-level constants
PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / \
               "data" / "hardware_profile.json"

# VRAM thresholds in GB
VRAM_TIER_90B = 60.0   # Llama 3.2-vision 90B needs ~55 GB minimum
VRAM_TIER_11B = 6.0    # Llama 3.2-vision 11B fits in 6-8 GB at Q4
VRAM_TIER_LITE = 4.0   # Moondream fits in 2-3 GB but needs headroom


# ── Public API ─────────────────────────────────────────────────────────────

def detect_gpu() -> dict:
    """Detect GPU vendor, model, and VRAM.

    Returns:
        dict with keys:
            has_gpu (bool)
            vendor (str): "NVIDIA", "AMD", "Intel", "Apple", or "unknown"
            model (str): GPU model name or empty string
            vram_gb (float): VRAM in gigabytes, 0.0 if unknown
            detection_method (str): which probe succeeded
            os (str): "Windows", "Darwin", "Linux"
    """
    result = {
        "has_gpu": False,
        "vendor": "unknown",
        "model": "",
        "vram_gb": 0.0,
        "detection_method": "none",
        "os": platform.system(),
    }

    # Try in order of reliability
    probes = [
        _probe_nvidia_smi,
        _probe_windows_wmic,
        _probe_macos_system_profiler,
        _probe_linux_lspci,
    ]
    for probe in probes:
        try:
            data = probe()
            if data and data.get("has_gpu"):
                data["os"] = result["os"]
                return data
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            continue
        except Exception:
            # Probe failed in unexpected way. Move on, don't crash detection.
            continue

    return result


def detect_vram_gb() -> float:
    """Convenience wrapper. Returns VRAM in GB, 0.0 if no GPU."""
    data = detect_gpu()
    return float(data.get("vram_gb", 0.0))


def recommend_ollama_model(
    vram_gb: Optional[float] = None,
    has_gpu: Optional[bool] = None,
) -> dict:
    """Pick the best Ollama model for the detected hardware.

    Args:
        vram_gb: Override VRAM. If None, runs detection.
        has_gpu: Override GPU presence. If None, runs detection.

    Returns:
        dict with keys:
            model (str | None): Ollama model name, or None if no local vision
            tier_label (str): human-readable tier name
            reason (str): one-line explanation
            disk_estimate_gb (float): rough disk for the model weights
            vram_required_gb (float): minimum VRAM for the model
    """
    if has_gpu is None or vram_gb is None:
        gpu_data = detect_gpu()
        has_gpu = gpu_data["has_gpu"]
        vram_gb = gpu_data["vram_gb"]

    if not has_gpu or vram_gb < VRAM_TIER_LITE:
        return {
            "model": None,
            "tier_label": "no_local_vision",
            "reason": (
                "No GPU detected or VRAM below 4 GB. "
                "DocTR will run CPU-only for OCR. "
                "Vision falls back directly to Gemini Tier 2."
            ),
            "disk_estimate_gb": 0.0,
            "vram_required_gb": 0.0,
        }

    if vram_gb >= VRAM_TIER_90B:
        return {
            "model": "llama3.2-vision:90b",
            "tier_label": "llama_vision_90b",
            "reason": (
                f"GPU has {vram_gb:.1f} GB VRAM. "
                "Using llama3.2-vision:90b for maximum local quality."
            ),
            "disk_estimate_gb": 55.0,
            "vram_required_gb": 55.0,
        }

    if vram_gb >= VRAM_TIER_11B:
        return {
            "model": "llama3.2-vision:11b",
            "tier_label": "llama_vision_11b",
            "reason": (
                f"GPU has {vram_gb:.1f} GB VRAM. "
                "Using llama3.2-vision:11b (recommended consumer-GPU default)."
            ),
            "disk_estimate_gb": 7.9,
            "vram_required_gb": 6.0,
        }

    return {
        "model": "moondream:1.8b",
        "tier_label": "moondream_lite",
        "reason": (
            f"GPU has {vram_gb:.1f} GB VRAM. "
            "Using moondream:1.8b lightweight vision model."
        ),
        "disk_estimate_gb": 1.7,
        "vram_required_gb": 2.5,
    }


def write_hardware_profile(profile_path: Optional[Path] = None) -> dict:
    """Run detection + recommendation and persist to data/hardware_profile.json.

    Returns the full profile dict that was written.
    """
    target = Path(profile_path) if profile_path else PROFILE_PATH

    gpu = detect_gpu()
    rec = recommend_ollama_model(
        vram_gb=gpu["vram_gb"],
        has_gpu=gpu["has_gpu"],
    )

    profile = {
        "schema_version": 1,
        "detected_at": _now_iso(),
        "gpu": gpu,
        "ollama_recommendation": rec,
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile


def read_hardware_profile(profile_path: Optional[Path] = None) -> Optional[dict]:
    """Read a previously written profile. Returns None if file missing."""
    target = Path(profile_path) if profile_path else PROFILE_PATH
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


# ── Internal probes ────────────────────────────────────────────────────────

def _probe_nvidia_smi() -> Optional[dict]:
    """Probe nvidia-smi. Works on Windows, Linux, macOS with NVIDIA driver."""
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            timeout=8,
        ).decode("utf-8", errors="ignore").strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None

    if not out:
        return None

    # nvidia-smi can list multiple GPUs. Take the first.
    first_line = out.splitlines()[0].strip()
    parts = [p.strip() for p in first_line.split(",")]
    if len(parts) < 2:
        return None
    name = parts[0]
    try:
        # memory.total reports MiB by default
        vram_mib = float(parts[1])
        vram_gb = vram_mib / 1024.0
    except ValueError:
        vram_gb = 0.0

    return {
        "has_gpu": True,
        "vendor": "NVIDIA",
        "model": name,
        "vram_gb": round(vram_gb, 2),
        "detection_method": "nvidia-smi",
    }


def _probe_windows_wmic() -> Optional[dict]:
    """Probe wmic on Windows. Works without an NVIDIA driver, picks up
    AMD and Intel cards. Less precise on VRAM (sometimes truncated)."""
    if platform.system() != "Windows":
        return None
    try:
        out = subprocess.check_output(
            [
                "wmic", "path", "win32_VideoController",
                "get", "AdapterRAM,Name", "/format:value",
            ],
            stderr=subprocess.DEVNULL,
            timeout=8,
        ).decode("utf-8", errors="ignore")
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None

    name = ""
    vram_bytes = 0
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Name="):
            name = line.split("=", 1)[1].strip()
        elif line.startswith("AdapterRAM="):
            v = line.split("=", 1)[1].strip()
            if v.isdigit():
                vram_bytes = max(vram_bytes, int(v))

    if not name:
        return None

    vendor = _vendor_from_name(name)
    vram_gb = vram_bytes / (1024.0 ** 3) if vram_bytes else 0.0

    return {
        "has_gpu": True,
        "vendor": vendor,
        "model": name,
        "vram_gb": round(vram_gb, 2),
        "detection_method": "wmic",
    }


def _probe_macos_system_profiler() -> Optional[dict]:
    """Probe system_profiler on macOS. Picks up Apple Silicon unified
    memory and discrete cards."""
    if platform.system() != "Darwin":
        return None
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).decode("utf-8", errors="ignore")
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None

    name = ""
    vram_gb = 0.0
    chipset_match = re.search(r"Chipset Model:\s*(.+)", out)
    if chipset_match:
        name = chipset_match.group(1).strip()
    vram_match = re.search(r"VRAM[^:]*:\s*([\d.]+)\s*(MB|GB)", out)
    if vram_match:
        amount = float(vram_match.group(1))
        unit = vram_match.group(2)
        vram_gb = amount / 1024.0 if unit == "MB" else amount

    # Apple Silicon does not always report VRAM. Use total system memory
    # as a soft proxy because unified memory is shared with the GPU.
    if vram_gb == 0.0 and "Apple" in name:
        try:
            mem_bytes = int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"],
                stderr=subprocess.DEVNULL,
                timeout=4,
            ).decode("utf-8").strip())
            # Apple Silicon GPU can use roughly 75 percent of unified RAM.
            vram_gb = (mem_bytes / (1024.0 ** 3)) * 0.75
        except (subprocess.SubprocessError, ValueError):
            pass

    if not name:
        return None

    return {
        "has_gpu": True,
        "vendor": _vendor_from_name(name),
        "model": name,
        "vram_gb": round(vram_gb, 2),
        "detection_method": "system_profiler",
    }


def _probe_linux_lspci() -> Optional[dict]:
    """Probe lspci on Linux. Detects presence and vendor but rarely
    reports VRAM. We mark VRAM as 0.0 in that case so the recommender
    can fall back to a CPU-safe choice."""
    if platform.system() != "Linux":
        return None
    try:
        out = subprocess.check_output(
            ["lspci", "-nnk"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8", errors="ignore")
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None

    name = ""
    for line in out.splitlines():
        if "VGA compatible controller" in line or "3D controller" in line:
            # Format: 0a:00.0 VGA compatible controller [0300]: NVIDIA ... [10de:2204]
            parts = line.split(":", 2)
            if len(parts) >= 3:
                name = parts[2].strip()
                break
    if not name:
        return None

    return {
        "has_gpu": True,
        "vendor": _vendor_from_name(name),
        "model": name,
        "vram_gb": 0.0,
        "detection_method": "lspci",
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _vendor_from_name(name: str) -> str:
    n = name.upper()
    if "NVIDIA" in n or "GEFORCE" in n or "RTX" in n or "GTX" in n \
            or "QUADRO" in n or "TESLA" in n:
        return "NVIDIA"
    if "AMD" in n or "RADEON" in n or "RX " in n or "VEGA" in n:
        return "AMD"
    if "INTEL" in n or "ARC " in n or "IRIS" in n or "UHD" in n or "HD GRAPHICS" in n:
        return "Intel"
    if "APPLE" in n or "M1" in n or "M2" in n or "M3" in n or "M4" in n:
        return "Apple"
    return "unknown"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── CLI entry point ────────────────────────────────────────────────────────

def _main() -> int:
    """Run detection from the command line. Used by the installer."""
    profile = write_hardware_profile()
    print(json.dumps(profile, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
