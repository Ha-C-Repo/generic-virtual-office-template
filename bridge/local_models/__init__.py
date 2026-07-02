"""Local model integration: DocTR (OCR) + Ollama (vision LLM).

Phase 7 of the post-parity roadmap (v4.0.0). Builds the local tier of
the three-tier vision pipeline so the Owner's Windows machine handles
page triage and OCR locally before Gemini ever sees a tile.

Tier layout (set at install time, runtime fallback safe):
    Tier 1: DocTR (CPU/GPU) + Ollama Llama 3.2-vision (the Owner's GPU)
    Tier 2: Gemini Flash 2.0 (cloud, current primary)
    Tier 3: GPT-4o (cloud, deterministic AISC math verifier)

This package owns Tier 1. The tier router that orchestrates 1 -> 2 -> 3
lives in bridge/drawing_intel/tier_router.py and is built in Phase 7b.

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .hardware_detector import (
    detect_gpu,
    detect_vram_gb,
    recommend_ollama_model,
    write_hardware_profile,
    read_hardware_profile,
)
from .ollama_client import (
    OllamaClient,
    is_ollama_running,
    pull_model_if_missing,
)
from .doctr_client import (
    DocTRClient,
    is_doctr_available,
)
from .installer_setup import (
    run_first_launch_setup,
    install_local_dependencies,
)

__all__ = [
    "detect_gpu",
    "detect_vram_gb",
    "recommend_ollama_model",
    "write_hardware_profile",
    "read_hardware_profile",
    "OllamaClient",
    "is_ollama_running",
    "pull_model_if_missing",
    "DocTRClient",
    "is_doctr_available",
    "run_first_launch_setup",
    "install_local_dependencies",
]
