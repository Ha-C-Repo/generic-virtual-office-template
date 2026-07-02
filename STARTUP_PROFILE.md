# E.1 - Startup Time Profile · v3.2.0

**Profiled:** 2026-05-08 · Python 3.12 · pywebview shell

## Cold-start measurement

| Stage | Time | Notes |
|---|---:|---|
| `import bridge.api` | 49.7 ms | Loads 5 bridge modules; rest lazy |
| `Bridge()` constructor | 0.0 ms | No-op - defers everything |
| `version()` first call | 0.2 ms | Returns dict literal |
| `get_panel_data()` | 1.0 ms | Reads `houston_pipeline_seed.json` (small) |
| **Total ready time** | **50.8 ms** | Chat input becomes interactive |

**Target:** <2 seconds · **Actual:** 50.8 ms · **Margin:** 39× headroom.

## Why so fast

Every heavy dependency is imported **inside the function that uses it**, never at module-top:

```python
# bridge/api.py - typical pattern
def export_project_card_pdf(self, project_data: dict = None) -> dict:
    try:
        from bridge.documents import generate_proposal   # lazy
        ...
```

Heavy modules verified absent at startup:

| Module | Use case | Loaded at startup? |
|---|---|---|
| `reportlab` | PDF generation (proposals, reports) | ❌ lazy |
| `pdfplumber` | PDF text extraction (auto-pipeline) | ❌ lazy |
| `yfinance` | Stock research agent | ❌ lazy |
| `numpy` / `pandas` | AISC math, data analysis | ❌ lazy |
| `easyocr` | Drawing vision fallback | ❌ lazy |
| `PIL` | Image handling | ❌ lazy |
| `ezdxf` | DXF drawing parsing | ❌ lazy |

## What loads at startup (the 50ms)

The 49.7ms import time is dominated by:

- `bridge.api` itself (4,995 lines, but mostly method definitions - Python parses fast)
- `bridge.constants` (rates, team routing, blocker definitions)
- `bridge.documents` constants (`STANDARD_EXCLUSIONS`, `PAYMENT_TERMS`, etc.) imported into `project_processor`
- Python stdlib: `json`, `datetime`, `pathlib`, `sqlite3`, `hashlib`, `functools`

No further optimization warranted - at 50.8 ms the user sees the chat input ready to type before they've finished blinking.

## Implication for EXE

The PyInstaller-packaged EXE will add ~1-2 seconds of disk I/O for the first launch (spinning the embedded interpreter + WebView2 paint). After warm cache, subsequent launches will run at the same 50.8 ms profile measured here.

**Estimated end-user cold start (EXE):** 1.5-2.0 seconds total (interpreter spin + this profile + WebView2 paint).

**Subsequent launches:** under 500 ms.

## Recommendation

No code changes needed. This profile becomes the regression baseline - if a future feature adds a top-level import of a heavy module, this number will jump and we'll know.

To re-run this profile manually:

```python
import time, sys
sys.path.insert(0, '.')
t0 = time.perf_counter()
from bridge.api import Bridge
print(f"{(time.perf_counter()-t0)*1000:.1f} ms")
```
