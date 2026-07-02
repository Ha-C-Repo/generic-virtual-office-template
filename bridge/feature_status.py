"""Feature status scanner (v6.1.2).

Scans all optional features at boot or on demand. Reports which are
active, which are scaffolded but waiting for deps/services, and which
have wiring bugs (Bridge method missing or wrong signature).

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import importlib
import logging

log = logging.getLogger(__name__)


# Each entry: (feature_name, category, check_function_name, fix_hint)
FEATURE_REGISTRY = [
    # External services
    ("OpenHuman Sidecar", "service", "_check_openhuman",
     "Install from tinyhumans.ai/openhuman. Runs at localhost:7788."),
    ("IDEA StatiCa Checkbot", "service", "_check_idea_statica",
     "Start IDEA StatiCa Checkbot. Runs at localhost:5000."),
    ("Ollama Local LLM", "service", "_check_ollama",
     "Install Ollama from ollama.com. Runs at localhost:11434."),

    # Python packages (optional features)
    ("Shop Floor QR Codes", "package", "_check_qrcode",
     "pip install qrcode[pil]"),
    ("Shop Floor Photo QC", "package", "_check_cv2",
     "pip install opencv-python-headless"),
    ("Drawing Visual Diff", "package", "_check_cv2_fitz",
     "pip install opencv-python-headless pymupdf"),
    ("BIM/IFC Import", "package", "_check_ifcopenshell",
     "pip install ifcopenshell"),
    ("CNC DXF Parts", "package", "_check_ezdxf",
     "pip install ezdxf"),
    ("CNC Punch Maps", "package", "_check_reportlab",
     "pip install reportlab"),
    ("Calc Pack Export", "package", "_check_openpyxl",
     "pip install openpyxl"),
    ("Project RAG (ChromaDB)", "package", "_check_chromadb",
     "pip install chromadb"),
    ("Objective Planner (CrewAI)", "package", "_check_crewai",
     "pip install crewai"),
    ("Takeoff Graph (LangGraph)", "package", "_check_langgraph",
     "pip install langgraph"),
    ("SMS Notifications (Twilio)", "package", "_check_twilio",
     "pip install twilio"),
    ("EIA Fuel Surcharge", "package", "_check_httpx",
     "pip install httpx"),
    ("OCR (docTR)", "package", "_check_doctr",
     "pip install python-doctr"),
    ("Stock Research", "package", "_check_yfinance",
     "pip install yfinance"),
    ("Steel Price Feed (FRED)", "package", "_check_fredapi",
     "pip install fredapi"),
]


def _try_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _check_openhuman() -> dict:
    try:
        from bridge.openhuman import OpenHumanClient
        c = OpenHumanClient(timeout=2)
        if c.is_available():
            status = c.get_status()
            return {"active": True, "detail": f"Connected. {status}"}
        return {"active": False, "detail": "Not running at localhost:7788"}
    except Exception as e:
        return {"active": False, "detail": str(e)[:80]}


def _check_idea_statica() -> dict:
    try:
        import requests
        r = requests.get("http://localhost:5000/health", timeout=2)
        return {"active": r.ok, "detail": "Connected" if r.ok else "Not responding"}
    except Exception:
        return {"active": False, "detail": "Not running at localhost:5000"}


def _check_ollama() -> dict:
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.ok:
            models = r.json().get("models", [])
            names = [m.get("name", "?") for m in models[:5]]
            return {"active": True, "detail": f"Connected. Models: {names}"}
        return {"active": False, "detail": "Not responding"}
    except Exception:
        return {"active": False, "detail": "Not running at localhost:11434"}


def _check_qrcode() -> dict:
    return {"active": _try_import("qrcode"), "detail": "qrcode package"}

def _check_cv2() -> dict:
    return {"active": _try_import("cv2"), "detail": "opencv-python"}

def _check_cv2_fitz() -> dict:
    has_cv2 = _try_import("cv2")
    has_fitz = _try_import("fitz")
    return {"active": has_cv2 and has_fitz,
            "detail": f"cv2={has_cv2}, fitz={has_fitz}"}

def _check_ifcopenshell() -> dict:
    return {"active": _try_import("ifcopenshell"), "detail": "ifcopenshell"}

def _check_ezdxf() -> dict:
    return {"active": _try_import("ezdxf"), "detail": "ezdxf"}

def _check_reportlab() -> dict:
    return {"active": _try_import("reportlab"), "detail": "reportlab"}

def _check_openpyxl() -> dict:
    return {"active": _try_import("openpyxl"), "detail": "openpyxl"}

def _check_chromadb() -> dict:
    return {"active": _try_import("chromadb"), "detail": "chromadb"}

def _check_crewai() -> dict:
    return {"active": _try_import("crewai"), "detail": "crewai"}

def _check_langgraph() -> dict:
    return {"active": _try_import("langgraph"), "detail": "langgraph"}

def _check_twilio() -> dict:
    return {"active": _try_import("twilio"), "detail": "twilio"}

def _check_httpx() -> dict:
    return {"active": _try_import("httpx"), "detail": "httpx"}

def _check_doctr() -> dict:
    return {"active": _try_import("doctr"), "detail": "doctr"}

def _check_yfinance() -> dict:
    return {"active": _try_import("yfinance"), "detail": "yfinance"}

def _check_fredapi() -> dict:
    return {"active": _try_import("fredapi"), "detail": "fredapi"}


# Lookup table for check functions
_CHECKERS = {
    "_check_openhuman": _check_openhuman,
    "_check_idea_statica": _check_idea_statica,
    "_check_ollama": _check_ollama,
    "_check_qrcode": _check_qrcode,
    "_check_cv2": _check_cv2,
    "_check_cv2_fitz": _check_cv2_fitz,
    "_check_ifcopenshell": _check_ifcopenshell,
    "_check_ezdxf": _check_ezdxf,
    "_check_reportlab": _check_reportlab,
    "_check_openpyxl": _check_openpyxl,
    "_check_chromadb": _check_chromadb,
    "_check_crewai": _check_crewai,
    "_check_langgraph": _check_langgraph,
    "_check_twilio": _check_twilio,
    "_check_httpx": _check_httpx,
    "_check_doctr": _check_doctr,
    "_check_yfinance": _check_yfinance,
    "_check_fredapi": _check_fredapi,
}


def scan_features() -> dict:
    """Scan all optional features and report status.

    Returns:
        {
            "active": [list of working features],
            "inactive": [list of scaffolded features with fix hints],
            "total": int,
            "active_count": int,
            "inactive_count": int,
        }
    """
    active = []
    inactive = []

    for name, category, checker_name, fix_hint in FEATURE_REGISTRY:
        checker = _CHECKERS.get(checker_name)
        if not checker:
            inactive.append({
                "name": name, "category": category,
                "status": "no_checker", "fix": fix_hint,
            })
            continue

        try:
            result = checker()
            if result.get("active"):
                active.append({
                    "name": name, "category": category,
                    "detail": result.get("detail", ""),
                })
            else:
                inactive.append({
                    "name": name, "category": category,
                    "status": result.get("detail", "inactive"),
                    "fix": fix_hint,
                })
        except Exception as e:
            inactive.append({
                "name": name, "category": category,
                "status": str(e)[:60], "fix": fix_hint,
            })

    return {
        "active": active,
        "inactive": inactive,
        "total": len(FEATURE_REGISTRY),
        "active_count": len(active),
        "inactive_count": len(inactive),
    }


def format_feature_report(scan: dict) -> str:
    """Format scan results as a readable report."""
    lines = [
        f"Feature Status: {scan['active_count']}/{scan['total']} active",
        "",
    ]

    if scan["active"]:
        lines.append("ACTIVE:")
        for f in scan["active"]:
            lines.append(f"  + {f['name']} ({f['category']}): {f.get('detail','')}")

    if scan["inactive"]:
        lines.append("")
        lines.append("INACTIVE (scaffolded, waiting for deps):")
        for f in scan["inactive"]:
            lines.append(f"  - {f['name']} ({f['category']}): {f.get('status','')}")
            lines.append(f"    Fix: {f['fix']}")

    return "\n".join(lines)


# vj-fix BUG-7: alias for docs/callers that reference scan_all_features
scan_all_features = scan_features
