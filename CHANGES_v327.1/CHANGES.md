# v3.2.7.1 - VJ Auto-Fix Bundle

Patch level over v3.2.7-final. Applied after the Owner's sandbox dry-run.
All changes are surgical. No new dependencies. No data migrations.

## Files Changed

| File | Purpose | Type |
|---|---|---|
| `bridge/blockers.py` | MC-01 disambiguate "Nd" -> "Nd open" in briefing summary | Modified |
| `bridge/calculators.py` | MC-02 tonnage-banded sanity gate thresholds + BUG-3 `total_burdened` alias (already present) | Modified |
| `bridge/compliance.py` | MC-03 escalated blockers now penalize compliance grade | Modified |
| `bridge/change_order.py` | MC-04 compatibility shim re-exports from `bridge.agents.change_order` | NEW |
| `bridge/diagnostics.py` | MC-05 lead with health verdict + adjusted score | Modified |
| `bridge/api.py` | BUG-4 `Bridge.morning_brief` alias appended | Modified |
| `bridge/agents/stock_research.py` | BUG-9 removed delisted "X" ticker | Modified |
| `bridge/data_sources.py` | BUG-9 same fix in fetch_watchlist | Modified |
| `bridge/takeoff_graph/graph.py` | BUG-8 default to threadpool fallback (LangGraph path needs reducers) | Modified |

## Verification After Apply

```
Before:  311/353 exercised checks pass | 1 fail (compliance_diff) | 4/18 features active
After:   313/354 exercised checks pass | 0 fails                 | 11/18 features active
```

## What Still Needs Owner (Roadmap)

See `OWNER_ROADMAP_v327_1.md` in the install root.
