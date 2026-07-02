"""SIM-08: Direct route for natural utterances.

Owner tested 21 natural utterances. Two matched. The rest fell through
to the AI fallback chain and crashed when API keys were missing. This
module sits in front of `ai_ask` and catches the common ones, dispatching
them directly to Bridge methods without any LLM call.

Design:
- Each entry is (compiled_regex, handler_callable, description).
- handler_callable signature: (bridge, match) -> dict | None
  Returns a chat-shaped dict (`text`, `provider`, `model`, `route`, `data`)
  or None to fall through.
- Try entries top-to-bottom. First match wins.
- No AI keys required for anything here.

Adding a new direct route is two lines: append to _ROUTES.
"""
from __future__ import annotations
import re
import threading as _threading
from typing import Callable, Optional


# ── HELPERS ───────────────────────────────────────────────────────────


def _fmt_local_response(text: str, route_label: str, data: dict | None = None) -> dict:
    """Standard local-response envelope so ai_ask gets a predictable shape."""
    out = {
        "text": text,
        "provider": "LOCAL",
        "model": "direct-route-v1",
        "route": route_label,
    }
    if data is not None:
        out["data"] = data
    return out


def _fmt_money(n) -> str:
    try:
        return f"${float(n):,.0f}"
    except Exception:
        return str(n)


def _clean_bid_name(raw: str) -> str:
    name = raw.replace('.json', '').replace('_', ' ')
    for suffix in ('YOUR COMPANY', 'INTERNAL', 'your company', 'internal'):
        name = name.replace(suffix, '').strip()
    return name.title().strip()


def _fmt_bids_table(bids: list) -> str:
    if not bids:
        return "  (none)"
    rows = []
    for b in bids[:25]:
        bid_id = b.get("id", b.get("bid_id", "?"))
        raw_name = b.get("name") or b.get("project_name") or "?"
        name = _clean_bid_name(raw_name)[:55]
        tons = b.get("tonnage", b.get("struct_tons", 0))
        val = b.get("estimated_value", b.get("total_bid", 0))
        state = b.get("state", b.get("status", "?"))
        rows.append(f"  #{bid_id:>3}  {name:<55}  {tons:>5} T  {_fmt_money(val):>9}  {state}")
    return "\n".join(rows)


# ── HANDLERS ──────────────────────────────────────────────────────────


def _h_list_bids(bridge, m) -> dict:
    r = bridge.list_active_bids()
    if not r.get("ok"):
        return _fmt_local_response(f"list_active_bids failed: {r.get('error')}", "list_bids (error)")
    d = r["data"]
    bids = d.get("bids", [])
    text = f"Active bids: {d.get('count', len(bids))}\n\n{_fmt_bids_table(bids)}"
    return _fmt_local_response(text, "list_bids", d)


def _h_compliance(bridge, m) -> dict:
    r = bridge.compliance_summary()
    if not r.get("ok"):
        return _fmt_local_response(f"compliance_summary failed: {r.get('error')}", "compliance (error)")
    d = r["data"]
    counts = d.get("counts", {})
    n_blocked = counts.get("blocked", 0)
    n_open = counts.get("open", 0)
    n_ok = counts.get("ok", 0)
    grade = d.get("grade", "?")
    score = d.get("score_pct", 0)
    text = f"{n_blocked} blocked / {n_open} open / {n_ok} ok / grade {grade} / {score:.1f}%"
    blockers = d.get("priority_blockers", [])
    if blockers:
        def _bt(b):
            if isinstance(b, dict):
                return b.get("item", b.get("title", b.get("name", str(b))))
            return str(b)
        text += "\n\nPriority blockers:\n" + "\n".join(f"  - {_bt(b)}" for b in blockers[:5])
    return _fmt_local_response(text, "compliance", d)


def _h_blockers(bridge, m) -> dict:
    r = bridge.get_blockers()
    if not r.get("ok"):
        return _fmt_local_response(f"get_blockers failed: {r.get('error')}", "blockers (error)")
    d = r["data"]
    bl = d.get("blockers", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    if bl:
        def _fmt_blocker(b):
            if isinstance(b, dict):
                title = b.get("title") or b.get("description") or str(b)
            else:
                title = str(b)
            return title.replace("—", "-").replace("–", "-").replace("→", "->")
        text = f"Blockers: {len(bl)}\n" + "\n".join(f"  - {_fmt_blocker(b)}" for b in bl[:10])
    else:
        text = "No active blockers."
    return _fmt_local_response(text, "blockers", d)


def _h_ar_aging(bridge, m) -> dict:
    r = bridge.get_ar_aging()
    if not r.get("ok"):
        return _fmt_local_response(f"get_ar_aging failed: {r.get('error')}", "ar_aging (error)")
    d = r["data"]
    text = "AR aging:\n"
    for bucket in ("current", "0_30", "30_60", "60_90", "90_plus", "total"):
        v = d.get(bucket)
        if v is not None:
            text += f"  {bucket:>10}: {_fmt_money(v)}\n"
    if "summary_line" in d:
        text += "\n" + d["summary_line"]
    return _fmt_local_response(text.rstrip(), "ar_aging", d)


def _h_shop_kpis(bridge, m) -> dict:
    r = bridge.get_shop_kpis(days=7)
    if not r.get("ok"):
        return _fmt_local_response(f"get_shop_kpis failed: {r.get('error')}", "shop_kpis (error)")
    d = r["data"]
    text = "Shop KPIs (last 7 days):\n"
    for k, v in d.items():
        if isinstance(v, (int, float, str)):
            text += f"  {k}: {v}\n"
    return _fmt_local_response(text.rstrip(), "shop_kpis", d)


def _h_shop_log(bridge, m) -> dict:
    r = bridge.get_shop_log(days=7)
    if not r.get("ok"):
        return _fmt_local_response(f"get_shop_log failed: {r.get('error')}", "shop_log (error)")
    d = r["data"]
    entries = d.get("entries", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    text = f"Shop log: {len(entries)} entries (last 7 days)\n" + "\n".join(f"  {e}" for e in entries[:20])
    return _fmt_local_response(text, "shop_log", d)


def _h_score_bid(bridge, m) -> dict:
    bid_id = int(m.group(1))
    r = bridge.pipeline_score(bid_id)
    if not r.get("ok"):
        return _fmt_local_response(f"pipeline_score({bid_id}) failed: {r.get('error')}", "score_bid (error)")
    d = r["data"]
    text = (
        f"Bid #{bid_id} ({d.get('name', '?')}): score {d.get('score', '?')}/100\n"
        f"State: {d.get('state', '?')}\n"
        f"Terminal: {d.get('terminal', '?')}\n"
    )
    factors = d.get("factors", [])
    if isinstance(factors, list) and factors:
        text += "\nFactors:\n" + "\n".join(
            f"  {f.get('label', '?')}: {f.get('delta', '?'):+d}" if isinstance(f, dict) else f"  {f}"
            for f in factors[:10]
        )
    elif isinstance(factors, dict) and factors:
        text += "\nFactors:\n" + "\n".join(f"  {k}: {v}" for k, v in list(factors.items())[:10])
    return _fmt_local_response(text, "score_bid", d)


def _h_advance_bid(bridge, m) -> dict:
    bid_id = int(m.group(1))
    old_state = "?"
    try:
        score_r = bridge.pipeline_score(bid_id)
        if score_r.get("ok"):
            old_state = score_r["data"].get("state", "?")
    except Exception:
        pass
    r = bridge.advance_bid(bid_id)
    if not r.get("ok"):
        return _fmt_local_response(f"advance_bid({bid_id}) failed: {r.get('error')}", "advance_bid (error)")
    d = r["data"]
    from_state = d.get("from_state", old_state)
    to_state = d.get("to_state", d.get("state", "?"))
    text = f"Bid #{bid_id} advanced.\n  from: {from_state}\n  to: {to_state}"
    return _fmt_local_response(text, "advance_bid", d)


def _h_quick_bid(bridge, m) -> dict:
    # m.group(1) = the full token string after "quick bid "
    body = m.group(1).strip()
    # Tokenize: find <num><suffix> tokens. Suffixes:
    #   t / ton / tons         -> struct_tons (first one)
    #   j / joist / joists     -> joist_tons (note: 22j means 22 tons of joists)
    #   sf / sqft              -> building_sf
    tons_re = re.compile(r"(\d+(?:\.\d+)?)\s*(t|ton|tons)\b", re.I)
    joist_re = re.compile(r"(\d+(?:\.\d+)?)\s*(j|joist|joists)\b", re.I)
    sf_re = re.compile(r"(\d+(?:\.\d+)?)\s*(sf|sqft|square\s*feet|square\s*foot)\b", re.I)

    struct_tons = 0.0
    joist_tons = 0.0
    building_sf = 0.0

    mt = tons_re.search(body)
    if mt:
        struct_tons = float(mt.group(1))
    mj = joist_re.search(body)
    if mj:
        joist_tons = float(mj.group(1))
    ms = sf_re.search(body)
    if ms:
        building_sf = float(ms.group(1))

    if struct_tons <= 0 and joist_tons <= 0:
        return _fmt_local_response(
            "quick bid: need tonnage. Example: `quick bid 65t 22j 38400sf`",
            "quick_bid (need input)",
        )
    if building_sf <= 0:
        return _fmt_local_response(
            f"quick bid: need building SF for $/SF computation.\n"
            f"Example: `quick bid {struct_tons:g}t "
            f"{joist_tons:g}j 38400sf`",
            "quick_bid (need sf)",
        )

    r = bridge.quick_bid_estimate(
        struct_tons=struct_tons,
        joist_tons=joist_tons,
        building_sf=building_sf,
        deck_sf=building_sf,  # treat building_sf as deck_sf when chat-shorthand is used
    )
    if not r.get("ok"):
        return _fmt_local_response(f"quick_bid_estimate failed: {r.get('error')}", "quick_bid (error)")
    d = r["data"]
    text = (
        f"Quick bid: {struct_tons:g}T struct + {joist_tons:g}T joists + {building_sf:,.0f} sf\n"
        f"  total: {_fmt_money(d.get('total_bid', 0))}\n"
        f"  $/sf: ${d.get('per_sf', 0):.2f}\n"
        f"  subtotal: {_fmt_money(d.get('subtotal', 0))}\n"
        f"  G&A: {_fmt_money(d.get('ga_overhead', 0))} ({d.get('ga_pct', 0)}%)\n"
        f"  rates: {d.get('rates_source', '?')}\n"
    )
    items = d.get("line_items", [])
    if items:
        text += "\nLine items:\n" + "\n".join(
            f"  {it.get('desc', '?')}: {_fmt_money(it.get('amount', 0))}  ({it.get('detail', '')})"
            for it in items[:8] if isinstance(it, dict)
        )
    gate = d.get("sanity_gate_3", {})
    if isinstance(gate, dict) and gate.get("status") and gate["status"] != "PASS":
        text += f"\n\nSanity gate: [{gate['status']}] {gate.get('warning', '')}"
    vm = d.get("vm_says")
    if vm:
        text += f"\n\nVirtual Owner: {vm}"
    return _fmt_local_response(text, "quick_bid", d)


def _h_calc_plate(bridge, m) -> dict:
    notation = m.group(1).strip()
    qty_str = m.group(2) if m.lastindex and m.lastindex >= 2 else None
    qty = int(qty_str) if qty_str else 1
    r = bridge.calculate_plate_weight(notation=notation, qty=qty)
    if not r.get("ok"):
        return _fmt_local_response(f"calculate_plate_weight failed: {r.get('error')}", "calc_plate (error)")
    d = r["data"]
    qty_note = f" x{qty}" if qty > 1 else ""
    text = (
        f"Plate {notation}{qty_note}:\n"
        f"  thickness: {d.get('thickness_in', '?')} in\n"
        f"  size: {d.get('width_in', '?')} x {d.get('length_in', '?')} in\n"
        f"  weight: {d.get('weight_total_lbs', 0):.1f} lbs ({d.get('weight_total_tons', 0):.4f} tons)\n"
    )
    return _fmt_local_response(text, "calc_plate", d)


def _h_change_orders(bridge, m) -> dict:
    r = bridge.get_change_orders()
    if not r.get("ok"):
        return _fmt_local_response(f"get_change_orders failed: {r.get('error')}", "change_orders (error)")
    d = r["data"]
    cos = d.get("change_orders", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    text = f"Change orders: {len(cos)}"
    if cos:
        text += "\n" + "\n".join(f"  - {co}" for co in cos[:10])
    return _fmt_local_response(text, "change_orders", d)


def _h_houston_pipeline(bridge, m) -> dict:
    r = bridge.get_houston_pipeline(top_n=5)
    if not r.get("ok"):
        return _fmt_local_response(f"get_houston_pipeline failed: {r.get('error')}", "houston_pipeline (error)")
    d = r["data"]
    bids = d.get("pipeline", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    text = f"Houston pipeline (top 5):\n{_fmt_bids_table(bids)}"
    return _fmt_local_response(text, "houston_pipeline", d)


def _h_fuel_surcharge(bridge, m) -> dict:
    r = bridge.get_fuel_surcharge()
    if not r.get("ok"):
        try:
            from bridge.eia_fuel_surcharge import get_cached
            cached = get_cached()
            if not cached.get("error"):
                price = cached.get("price_per_gallon", "?")
                date = cached.get("date", "?")
                surcharge = cached.get("surcharge_per_mile", "?")
                return _fmt_local_response(
                    f"EIA API unavailable. Last cached: ${price}/gal as of {date}\n"
                    f"  surcharge/mile: ${surcharge}",
                    "fuel_surcharge (cached)", cached
                )
        except Exception:
            pass
        return _fmt_local_response(
            f"Fuel surcharge unavailable: {r.get('error')}\n"
            f"  Check EIA API connectivity or set EIA_API_KEY env var.",
            "fuel_surcharge (error)"
        )
    d = r["data"]
    text = "Fuel surcharge:\n"
    for k, v in d.items():
        if isinstance(v, (int, float, str)):
            text += f"  {k}: {v}\n"
    return _fmt_local_response(text.rstrip(), "fuel_surcharge", d)


def _h_self_test(bridge, m) -> dict:
    # P20.1: pywebview bridge callbacks can run with a different cwd than
    # the project root. Some test helpers open SQLite with paths derived
    # from __file__ (absolute), but the OS may sandbox file writes differently
    # per-thread on Windows. Forcing cwd to the project root before the test
    # battery ensures all write paths resolve identically whether called from
    # the GUI or the RPC endpoint.
    import os
    _saved = os.getcwd()
    try:
        if getattr(sys, 'frozen', False):
            # Frozen: use LOCALAPPDATA (writable user data root)
            _test_cwd = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "YourCompany", "VirtualOffice"
            )
            os.makedirs(_test_cwd, exist_ok=True)
        else:
            # Source: project root (C:\Users\YourUser\.claude\projects\Cowork Virtual Office)
            from pathlib import Path as _Path
            _test_cwd = str(_Path(__file__).resolve().parent.parent)
        os.chdir(_test_cwd)
        r = bridge.run_self_test()
    finally:
        try:
            os.chdir(_saved)
        except Exception:
            pass
    if not r.get("ok"):
        return _fmt_local_response(f"run_self_test failed: {r.get('error')}", "self_test (error)")
    d = r["data"]
    text = (
        f"Self-test: {d.get('passed', '?')}/{d.get('total', '?')} pass · "
        f"{d.get('failed', '?')} fail · {d.get('skipped', '?')} skip · "
        f"health {d.get('health_pct', '?')}%"
    )
    return _fmt_local_response(text, "self_test", d)


# v3.2.7.15: VJ scan handlers. These kick off the scan in a background
# thread so the UI thread can return instantly. Without this the UI
# freezes for 60-180s and Windows marks the window "(Not Responding)".
# Prod evidence: May 14 2026 17:21 → 17:32 freeze on the Owner's machine
# typing "VJ scan and fix" with PROD pipeline error already on screen.
def _h_vj_scan(bridge, m) -> dict:
    """Kick off a read-only VJ scan (background)."""
    r = bridge.vj_scan_async()
    if not r.get("ok"):
        return _fmt_local_response(f"vj_scan_async failed: {r.get('error')}", "vj_scan (error)")
    d = r["data"]
    job_id = d.get("job_id", "?")
    eta = d.get("eta_sec", 30)
    text = (
        f"VJ scan started (job: {job_id}). ETA ~{eta}s.\n"
        f"Type 'vj status' to check progress, or 'vj result {job_id}' to fetch the report."
    )
    return _fmt_local_response(text, "vj_scan", d)


def _h_vj_scan_and_fix(bridge, m) -> dict:
    """Kick off VJ scan-and-fix (background, applies safe auto-fixes)."""
    # Pattern may capture 'fast' as a flag in group 1
    fast = False
    try:
        if m and m.lastindex and m.group(1):
            fast = "fast" in (m.group(1) or "").lower()
    except (IndexError, AttributeError):
        fast = False
    r = bridge.vj_scan_and_fix_async(fast_mode=fast)
    if not r.get("ok"):
        return _fmt_local_response(f"vj_scan_and_fix_async failed: {r.get('error')}", "vj_scan_and_fix (error)")
    d = r["data"]
    job_id = d.get("job_id", "?")
    eta = d.get("eta_sec", 60)
    mode = " (fast mode)" if fast else ""
    text = (
        f"VJ scan-and-fix started{mode} (job: {job_id}). ETA ~{eta}s.\n"
        f"Running in background, UI stays responsive.\n"
        f"Type 'vj status' to check, or 'vj result {job_id}' for the full report."
    )
    return _fmt_local_response(text, "vj_scan_and_fix", d)


def _h_vj_status(bridge, m) -> dict:
    """Poll all live VJ scan jobs."""
    r = bridge.poll_vj_scan()
    if not r.get("ok"):
        return _fmt_local_response(f"poll_vj_scan failed: {r.get('error')}", "vj_status (error)")
    d = r["data"]
    jobs = d.get("jobs", [])
    if not jobs:
        return _fmt_local_response("VJ: idle. No scans in flight.", "vj_status", d)
    lines = ["VJ scan jobs:"]
    for j in jobs:
        status = "done (poll for result)" if j.get("done") else "running"
        lines.append(f"  - {j.get('job_id', '?')}: {status}")
    return _fmt_local_response("\n".join(lines), "vj_status", d)


def _h_vj_result(bridge, m) -> dict:
    """Fetch the result for a specific VJ scan job by id."""
    job_id = m.group(1).strip() if m and m.lastindex else ""
    r = bridge.poll_vj_scan(job_id=job_id)
    if not r.get("ok"):
        return _fmt_local_response(f"poll_vj_scan({job_id}) failed: {r.get('error')}", "vj_result (error)")
    d = r["data"]
    if d.get("status") == "scanning":
        return _fmt_local_response(f"Job {job_id} still running. Try again in a few seconds.", "vj_result", d)
    # Full report came back - format the high-points
    if "clean" in d:
        # vj_scan_and_fix or vj_scan response
        clean = d.get("clean")
        issues = d.get("issues_found", d.get("issues", []))
        if isinstance(issues, list):
            issues_n = len(issues)
        else:
            issues_n = issues
        fixes = d.get("fixes_applied", 0)
        files_scanned = d.get("files_scanned", "?")
        scan_ms = d.get("scan_ms", 0)
        if scan_ms:
            duration_s = scan_ms / 1000
            if duration_s < 60:
                duration_str = f"{duration_s:.1f}s"
            else:
                duration_str = f"{int(duration_s // 60)}m {int(duration_s % 60)}s"
        else:
            duration_str = None
        text = (
            f"VJ {job_id}: {'CLEAN' if clean else 'ISSUES'}\n"
            f"  files scanned: {files_scanned}\n"
            f"  issues found:  {issues_n}\n"
            f"  fixes applied: {fixes}"
        )
        if duration_str:
            text += f"\n  duration:      {duration_str}"
        return _fmt_local_response(text, "vj_result", d)
    return _fmt_local_response(f"VJ {job_id}: result returned (see data block).", "vj_result", d)


def _h_aisc_weight(bridge, m) -> dict:
    """Focused weight-per-foot query: 'W14X82 weight' / 'weight of W14X82'."""
    shape = m.group(1).upper().replace("×", "X")
    try:
        r = bridge.get_aisc_member_info(designation=shape)
    except TypeError:
        r = bridge.get_aisc_member_info(shape)
    if not r.get("ok"):
        return _fmt_local_response(f"AISC lookup for {shape} failed: {r.get('error')}", "aisc_weight (error)")
    d = r["data"]
    wpf = d.get("weight_per_ft_lb", "N/A")
    return _fmt_local_response(f"{shape}: {wpf} lb/ft", "aisc_weight", d)


def _h_aisc_lookup(bridge, m) -> dict:
    shape = m.group(1).upper().replace("×", "X")
    # try get_aisc_member_info first (uses `designation` per SIM-07 inventory)
    try:
        r = bridge.get_aisc_member_info(designation=shape)
    except TypeError:
        # fallback for older signature
        r = bridge.get_aisc_member_info(shape)
    if not r.get("ok"):
        # SJI joist passthrough: not in AISC v16.0 CSV but valid on Your Company bids
        try:
            from bridge.aisc_validator import AISCValidator
            v = AISCValidator()
            vr = v.validate_shape(shape)
            if vr.get("valid") and vr.get("confidence") == "non-aisc-passthrough":
                source = vr.get("source", "non-AISC")
                msg = vr.get("message", f"{shape} recognized as {source}.")
                return _fmt_local_response(
                    f"{shape} - {source}\n{msg}\n"
                    f"No weight-per-foot data in AISC v16.0. "
                    f"Consult SJI Standard Specification for load tables.",
                    "aisc_lookup",
                    vr,
                )
        except Exception:
            pass
        return _fmt_local_response(f"AISC lookup for {shape} failed: {r.get('error')}", "aisc_lookup (error)")
    d = r["data"]
    text = f"AISC {shape}:\n"
    for k in ("type", "depth_in", "flange_width_in", "flange_thickness_in",
              "web_thickness_in", "weight_per_ft_lb", "area_sq_in"):
        if k in d:
            text += f"  {k}: {d[k]}\n"
    return _fmt_local_response(text.rstrip(), "aisc_lookup", d)


def _h_morning_brief(bridge, m) -> dict:
    """Morning briefing via direct route.

    Delegates to Bridge.morning_briefing() so data path resolution is
    identical to the STATUS tab and COMPLIANCE tile. Prior version called
    individual bridge methods which resolved paths differently in frozen mode.
    """
    from datetime import datetime
    header = f"Good morning. {datetime.now().strftime('%A, %B %d')}"
    try:
        r = bridge.morning_briefing()
        if not (r and r.get("ok")):
            return _fmt_local_response(
                f"{header}\n\nBriefing unavailable: {r.get('error', 'no response')}",
                "morning_brief",
            )
        d = r["data"]
        lines = [header, ""]

        # Blockers
        try:
            bl_r = bridge.get_blockers()
            if bl_r.get("ok"):
                bl = bl_r["data"]
                if isinstance(bl, dict):
                    bl = bl.get("blockers", [])
                if not isinstance(bl, list):
                    bl = []
                if bl:
                    lines.append(f"BLOCKERS ({len(bl)} active):")
                    for b in bl[:3]:
                        title = (b.get("title") or b.get("description") or str(b)) if isinstance(b, dict) else str(b)
                        title = title.replace("—", "-").replace("–", "-")
                        lines.append(f"  - {title}")
                else:
                    lines.append("BLOCKERS: None")
        except Exception:
            lines.append("BLOCKERS: (unavailable)")
        lines.append("")

        # Compliance - P21.2: counts live under data["counts"], not at data root.
        # compliance_summary() returns {"counts": {"blocked": N, "open": N, "ok": N, ...}}
        try:
            comp = bridge.compliance_summary()
            if comp.get("ok"):
                cd = comp.get("data", {})
                counts = cd.get("counts", {})
                n_blocked = counts.get("blocked", 0)
                n_open = counts.get("open", 0)
                n_ok = counts.get("ok", 0)
                grade = cd.get("grade", "?")
                score = cd.get("score_pct", 0)
                lines.append(
                    f"COMPLIANCE: {n_blocked} blocked / {n_open} open / {n_ok} ok"
                    f" / grade {grade} / {score:.1f}%"
                )
        except Exception:
            pass
        lines.append("")

        # Pipeline from morning_briefing() data (same source as STATUS tab)
        pipeline = d.get("pipeline", {})
        if pipeline:
            lines.append("PIPELINE: " + ", ".join(f"{s}: {n}" for s, n in pipeline.items()))
        recent = d.get("recent_bids", [])
        if recent:
            lines.append("")
            lines.append("RECENT BIDS:")
            for b in recent[:3]:
                lines.append(f"  [{b.get('id','?')}] {b.get('name','(unnamed)')} - {b.get('state','?')}")

        return _fmt_local_response("\n".join(lines), "morning_brief")
    except Exception as exc:
        return _fmt_local_response(f"{header}\n\nBriefing error: {exc}", "morning_brief")


def _h_stock_watchlist(bridge, m) -> dict:
    r = bridge.get_stock_watchlist()
    if not r.get("ok"):
        return _fmt_local_response(f"get_stock_watchlist failed: {r.get('error')}", "stock_watchlist (error)")
    d = r["data"]
    watchlist = d.get("watchlist", d.get("stocks", [])) if isinstance(d, dict) else d
    text = f"Stock watchlist ({len(watchlist) if isinstance(watchlist, list) else '?'} tickers):"
    if isinstance(watchlist, list):
        for s in watchlist[:15]:
            if isinstance(s, dict):
                tk = s.get("ticker", s.get("symbol", "?"))
                px = s.get("price", s.get("close", "?"))
                ch = s.get("change_pct", s.get("pct_change", ""))
                text += f"\n  {tk:<6} {px}  {ch}"
            else:
                text += f"\n  {s}"
    return _fmt_local_response(text, "stock_watchlist", d)


def _h_steel_prices(bridge, m) -> dict:
    r = bridge.get_steel_prices()
    if not r.get("ok"):
        return _fmt_local_response(f"get_steel_prices failed: {r.get('error')}", "steel_prices (error)")
    d = r["data"]
    text = "Steel prices:\n"
    for k, v in d.items():
        if isinstance(v, (int, float)):
            text += f"  {k}: {v}\n"
        elif isinstance(v, str) and len(v) < 80:
            text += f"  {k}: {v}\n"
    return _fmt_local_response(text.rstrip(), "steel_prices", d)


def _h_market(bridge, m) -> dict:
    r = bridge.get_market_dashboard()
    if not r.get("ok"):
        return _fmt_local_response(f"get_market_dashboard failed: {r.get('error')}", "market (error)")
    d = r["data"]
    text = "Market dashboard:\n"
    stats = d.get("stats", {})
    if isinstance(stats, dict):
        for k, v in stats.items():
            text += f"  {k}: {v}\n"
    return _fmt_local_response(text.rstrip(), "market", d)


def _h_macro(bridge, m) -> dict:
    r = bridge.get_macro_indicators()
    if not r.get("ok"):
        return _fmt_local_response(f"get_macro_indicators failed: {r.get('error')}", "macro (error)")
    d = r["data"]
    text = "Macro indicators:\n"
    indicators = d.get("indicators", d) if isinstance(d, dict) else {}
    if isinstance(indicators, dict):
        for k, v in indicators.items():
            if isinstance(v, dict):
                val = v.get("value", v.get("latest", "?"))
                text += f"  {k}: {val}\n"
            else:
                text += f"  {k}: {v}\n"
    return _fmt_local_response(text.rstrip(), "macro", d)


def _h_stock_brief(bridge, m) -> dict:
    ticker = m.group(1).upper()
    r = bridge.get_stock_brief(ticker)
    if not r.get("ok"):
        return _fmt_local_response(f"get_stock_brief({ticker}) failed: {r.get('error')}", "stock_brief (error)")
    d = r["data"]
    text = f"Stock brief: {ticker}\n"
    for k, v in d.items():
        if isinstance(v, (int, float, str)) and len(str(v)) < 120:
            text += f"  {k}: {v}\n"
    return _fmt_local_response(text.rstrip(), "stock_brief", d)


def _h_rates_query(bridge, m) -> dict:
    """Return locked Q2 2026 bid rates from bid_rates.py without an LLM call."""
    from bridge.bid_rates import BID_RATES
    fab    = BID_RATES.get("fab_per_ton", 0)
    erect  = BID_RATES.get("erection_per_ton", 0)
    joists = BID_RATES.get("joists_per_ton", 0)
    deck   = BID_RATES.get("roof_deck_per_sf", 0)
    anchor = BID_RATES.get("anchor_rod_1x20_each", 0)
    ga     = BID_RATES.get("ga_overhead_pct", 0)
    text = (
        f"Q2 2026 locked rates:\n"
        f"  Fabrication:  ${fab:,.0f}/ton\n"
        f"  Erection:     ${erect:,.0f}/ton\n"
        f"  Joists:       ${joists:,.0f}/ton\n"
        f"  Roof deck:    ${deck:.2f}/SF\n"
        f"  Anchor bolts: ${anchor:.0f}/ea\n"
        f"  G&A overhead: {ga * 100:.1f}%\n"
        f"  Net GP target: 25%"
    )
    return _fmt_local_response(text, "rates_query")


def _h_help(bridge, m) -> dict:
    """Show available direct routes. the Owner's chat-shortcut menu."""
    text = "Local chat commands (no API key needed):\n\n"
    seen = set()
    for _r in _ROUTES:
        desc = _r[2]
        if desc in seen:
            continue
        seen.add(desc)
        text += f"  - {desc}\n"
    text += "\nAnything else falls through to AI (requires API keys)."
    return _fmt_local_response(text, "help", {"routes": list_direct_routes()})


def _h_version(bridge, m) -> dict:
    r = bridge.version()
    if not r.get("ok"):
        return _fmt_local_response(f"version failed: {r.get('error')}", "version (error)")
    d = r["data"]
    text = f"Version: {d.get('version', '?')}"
    if "build" in d: text += f"\nBuild: {d['build']}"
    if "release_date" in d: text += f"\nReleased: {d['release_date']}"
    return _fmt_local_response(text, "version", d)


def _h_vendor_whitelist(bridge, m) -> dict:
    r = bridge.get_vendor_whitelist()
    if not r.get("ok"):
        return _fmt_local_response(f"get_vendor_whitelist failed: {r.get('error')}", "vendor_whitelist (error)")
    d = r["data"]
    vendors = d.get("whitelist", []) if isinstance(d, dict) else []
    lines = [f"Approved vendors ({len(vendors)}):"]
    for v in vendors:
        name = v.get("vendor_name", "?")
        vtype = v.get("vendor_type", "")
        loc = v.get("location", "")
        lines.append(f"  - {name} ({vtype}) {loc}")
    return _fmt_local_response("\n".join(lines), "vendor_whitelist", d)


def _h_vendor_quotes(bridge, m) -> dict:
    r = bridge.get_vendor_quotes()
    if not r.get("ok"):
        return _fmt_local_response(f"get_vendor_quotes failed: {r.get('error')}", "vendor_quotes (error)")
    d = r["data"]
    quotes = d.get("quotes", []) if isinstance(d, dict) else []
    count = d.get("count", len(quotes)) if isinstance(d, dict) else len(quotes)
    if not quotes:
        return _fmt_local_response("No vendor quotes on file. Type 'poll vendors' to request quotes.", "vendor_quotes", d)
    lines = [f"Vendor quotes ({count}):"]
    for q in quotes[:10]:
        vendor = q.get("vendor_name", "?")
        proj = q.get("project", "?")
        amt = q.get("amount", "?")
        lines.append(f"  - {vendor}: {proj} ${amt}")
    return _fmt_local_response("\n".join(lines), "vendor_quotes", d)


def _h_model_routing(bridge, m) -> dict:
    r = bridge.get_model_routing()
    if not r.get("ok"):
        return _fmt_local_response(f"get_model_routing failed: {r.get('error')}", "model_routing (error)")
    d = r["data"]
    tiers = d.get("tiers", {}) if isinstance(d, dict) else {}
    lines = ["AI model routing:"]
    for tier, info in tiers.items():
        if isinstance(info, dict):
            model = info.get("model", "?")
            label = info.get("label", tier)
            best = info.get("best_for", "")
            lines.append(f"  T{tier}: {label} ({model})")
            if best:
                lines.append(f"    Best for: {best[:60]}")
    return _fmt_local_response("\n".join(lines), "model_routing", d)


def _h_mcp_status(bridge, m) -> dict:
    r = bridge.mcp_status()
    if not r.get("ok"):
        return _fmt_local_response(f"mcp_status failed: {r.get('error')}", "mcp_status (error)")
    d = r["data"]
    http_r = bridge.mcp_http_server_status()
    http_d = http_r.get("data", {}) if http_r.get("ok") else {}
    running = http_d.get("running", False) if isinstance(http_d, dict) else False
    token_r = bridge.get_mcp_token()
    token_d = token_r.get("data", {}) if token_r.get("ok") else {}
    fingerprint = token_d.get("fingerprint", "?") if isinstance(token_d, dict) else "?"
    tunnel_r = bridge.get_tunnel_status()
    tunnel_d = tunnel_r.get("data", {}) if tunnel_r.get("ok") else {}
    tunnel_url = tunnel_d.get("url") if isinstance(tunnel_d, dict) else None
    lines = [
        f"MCP HTTP server: {'running' if running else 'stopped'}",
        f"Token fingerprint: {fingerprint}",
        f"Cloudflare tunnel: {tunnel_url or 'not running'}",
    ]
    config_exists = d.get("config_exists", False) if isinstance(d, dict) else False
    lines.append(f"Claude Desktop config: {'found' if config_exists else 'not found'}")
    return _fmt_local_response("\n".join(lines), "mcp_status", d)


def _h_mcp_token(bridge, m) -> dict:
    r = bridge.get_mcp_token()
    if not r.get("ok"):
        return _fmt_local_response(f"get_mcp_token failed: {r.get('error')}", "mcp_token (error)")
    d = r["data"]
    fingerprint = d.get("fingerprint", "?") if isinstance(d, dict) else "?"
    header = d.get("header_value", "") if isinstance(d, dict) else ""
    text = f"MCP token fingerprint: {fingerprint}\nAuthorization header: {header[:50]}..."
    return _fmt_local_response(text, "mcp_token", d)


def _h_bid_stl_generate(bridge, m) -> dict:
    """Generate 3d_model.stl from a bid's takeoff.json via chat command."""
    bn = m.group(1).upper()
    r = bridge.generate_bid_stl(bn, "")
    if not r.get("ok"):
        return _fmt_local_response(
            f"Cannot build STL for {bn}: {r.get('error')}",
            "bid_stl_generate (error)",
        )
    d = r["data"]
    return _fmt_local_response(
        f"STL built for {bn}: {d['member_count']} members, "
        f"{d['size_kb']} KB. Open MODEL tab to view.",
        "bid_stl_generate",
        d,
    )


def _h_vendor_poll(bridge, m) -> dict:
    r = bridge.poll_vendor_mailbox(force=True)
    if not r.get("ok"):
        return _fmt_local_response(f"poll_vendor_mailbox failed: {r.get('error')}", "vendor_poll (error)")
    d = r["data"]
    quotes_found = 0
    status = "done"
    if isinstance(d, dict):
        quotes_found = d.get("quotes_found", d.get("new_quotes", d.get("count", 0)))
        status = d.get("status", "done")
    text = f"Vendor poll: {quotes_found} new quote(s). Status: {status}"
    return _fmt_local_response(text, "vendor_poll", d)


def _h_emr_predict(bridge, m) -> dict:
    r = bridge.predict_emr()
    if not r.get("ok"):
        return _fmt_local_response(f"predict_emr failed: {r.get('error')}", "emr_predict (error)")
    d = r["data"]
    prediction = d.get("prediction", {}) if isinstance(d, dict) else {}
    gates = d.get("gates", {}) if isinstance(d, dict) else {}
    emr = prediction.get("emr", prediction.get("predicted_emr", "?")) if isinstance(prediction, dict) else "?"
    gate_pass = gates.get("eligible", gates.get("bid_eligible", "?")) if isinstance(gates, dict) else "?"
    text = f"EMR prediction: {emr}\nBid eligible: {gate_pass}"
    if isinstance(prediction, dict):
        for k, v in prediction.items():
            if k not in ("emr", "predicted_emr") and isinstance(v, (int, float, str)):
                text += f"\n  {k}: {v}"
    return _fmt_local_response(text, "emr_predict", d)


def _h_review_bid(bridge, m) -> dict:
    project = m.group(1).strip()
    tons = float(m.group(2))
    sf = float(m.group(3))
    margin_pct = float(m.group(4)) / 100.0
    # WARN-02 fix: synthesize bid_total for VM rule checking only (not a real
    # quote). Rate is intentionally set above BID_RATES.fab_per_ton ($3,750)
    # to avoid triggering a false "below market" GP margin rejection on this
    # rough check. The VM's structural rule checks (deck scope, PEMB,
    # exclusions) are what matter here. For binding reviews, callers should
    # use Bridge.review_bid(bid=real_dict) with actual line items.
    try:
        from bridge.bid_rates import BID_RATES as _br
        rate_per_ton = float(_br.get("fab_per_ton", 3750)) * 2.0
    except Exception:
        rate_per_ton = 7500  # fallback if BID_RATES unavailable
    bid_total = tons * rate_per_ton
    # P21.1: VirtualOwner.review() requires a text_content field to run
    # its 26 rules (deck check, PEMB scan, em-dash scan, etc.). Build a
    # synthetic proposal from the structured fields so all rules fire.
    synthetic_text = (
        f"PROPOSAL - {project}\n\n"
        f"Structural steel scope:\n"
        f"  Project:   {project}\n"
        f"  GC:        TBD\n"
        f"  Tonnage:   {tons} T\n"
        f"  Deck:      {sf:,.0f} SF (B-deck, supply and install)\n"
        f"  Total bid: ${bid_total:,.0f}\n"
        f"  GP target: {margin_pct*100:.1f}%\n"
    )
    bid = {
        "text_content": synthetic_text,
        "name": project,
        "tons": tons,
        "deck_sf": sf,
        "bid_total": bid_total,
        "margin_pct": margin_pct,
        "scope": ["structural steel", "erection"],
    }
    r = bridge.review_bid(bid=bid)
    if not r.get("ok"):
        return _fmt_local_response(f"review_bid failed: {r.get('error')}", "review_bid (error)")
    d = r["data"]
    text = (
        f"Review of '{project}' ({tons}T, {sf:,.0f} sf, {margin_pct*100:.1f}% margin):\n"
        f"  verdict: {d.get('verdict', '?')}\n"
        f"  approved: {d.get('approved', '?')}\n"
        f"  confidence: {d.get('confidence', '?')}\n"
        f"  note: rough-check rate ${rate_per_ton:.0f}/ton (2x fab). For binding review use Bridge.review_bid(bid=real_dict).\n"
    )
    issues = d.get("issues", [])
    if issues:
        text += "\nIssues:\n" + "\n".join(
            f"  [{i.get('severity', '?'):>4}] {i.get('rule', '?')}: {i.get('detail', '?')}"
            if isinstance(i, dict) else f"  {i}"
            for i in issues[:10]
        )
    return _fmt_local_response(text, "review_bid", d)


# ── ROUTE TABLE ───────────────────────────────────────────────────────
# Order matters: more specific patterns first. The first match wins.

_ROUTES: list[tuple] = [
    # Parameterized commands FIRST (more specific)
    (re.compile(r"^\s*score\s+bid\s+#?(\d+)\s*$", re.I), _h_score_bid, "score bid N"),
    (re.compile(r"^\s*advance\s+bid\s+#?(\d+)\s*$", re.I), _h_advance_bid, "advance bid N"),
    # quick bid: any combination of tons/joists/sf with their suffixes.
    # Parser sits in _h_quick_bid; regex just captures the tail.
    (
        re.compile(r"^\s*quick\s+bid\s+(.+?)\s*$", re.I),
        _h_quick_bid,
        "quick bid <tons>t <joist_tons>j <sf>sf",
    ),
    # plate: "calc plate PL1/2X12X12" / "plate weight PL.5X12X12 x24"
    (
        re.compile(
            r"^\s*(?:calc(?:ulate)?\s+)?plate\s+(?:weight\s+)?"
            r"([A-Za-z0-9/.\-x×X]+)"
            r"(?:\s+x(\d+))?\s*$",
            re.I,
        ),
        _h_calc_plate,
        "calc plate <notation> [xQty]",
    ),
    # Weight queries: "W14X82 weight" / "weight of W14X82"
    (
        re.compile(
            r"^\s*([WHSLCMP]+(?:T|S|HP|MC)?\d+[Xx×][\w/.]+)\s+weight\s*[?.!]?\s*$",
            re.I,
        ),
        _h_aisc_weight,
        "<shape> weight",
    ),
    (
        re.compile(
            r"^\s*weight\s+of\s+([WHSLCMP]+(?:T|S|HP|MC)?\d+[Xx×][\w/.]+)\s*[?.!]?\s*$",
            re.I,
        ),
        _h_aisc_weight,
        "weight of <shape>",
    ),
    # AISC lookup: "what is W12X26" / "lookup W12X26" / "info on HSS6X6X1/4"
    (
        re.compile(
            r"^\s*(?:what\s+is\s+|lookup\s+|info\s+on\s+|aisc\s+)"
            r"([WHSLCMP]+(?:T|S|HP|MC)?\d+[Xx×][\w/.]+)\s*$",
            re.I,
        ),
        _h_aisc_lookup,
        "what is <shape> / lookup <shape>",
    ),
    # SJI joist lookup: "aisc 18K5" / "lookup 18K5" / "what is LH10"
    (
        re.compile(
            r"^\s*(?:what\s+is\s+|lookup\s+|info\s+on\s+|aisc\s+)"
            r"(\d+K\d+|LH\d+|DLH\d+)\s*$",
            re.I,
        ),
        _h_aisc_lookup,
        "what is <joist> / lookup <SJI joist>",
    ),
    # STL generation from takeoff: "build 3d for PRJ-2026-ICD-009"
    (
        re.compile(
            r"^\s*(?:build|gen(?:erate)?|make)\s+(?:the\s+)?(?:3d|stl)\s+(?:for\s+)?"
            r"(NC-?\d{4}-?[A-Z]{2,4}-?\d{3,4})\s*$",
            re.I,
        ),
        _h_bid_stl_generate,
        "build|gen 3d/stl for NC-YYYY-XXX-### -> writes 3d_model.stl from takeoff",
        30.0,
    ),
    # review_bid parameterized: "review bid for ICD Church 1500t 250000sf 18%"
    (
        re.compile(
            r"^\s*review\s+bid\s+(?:for\s+)?(.+?)\s+(\d+(?:\.\d+)?)\s*(?:t|ton|tons)\s+"
            r"(\d+(?:\.\d+)?)\s*(?:sf|sqft)\s+(\d+(?:\.\d+)?)\s*%\s*$",
            re.I,
        ),
        _h_review_bid,
        "review bid for <project> <tons>t <sf>sf <margin>%",
    ),

    # Bid rate queries - static lookup, no LLM needed
    (re.compile(
        r"^\s*(?:"
        r"bid\s+rates?|current\s+rates?|fab\s+rates?|erection\s+rates?|"
        r"joist\s+rates?|deck\s+rates?|anchor\s+rates?|"
        r"show\s+(?:me\s+)?rates?|what\s+are\s+(?:the\s+)?(?:bid\s+)?rates?|"
        r"pricing\s+rates?|our\s+rates?"
        r")\s*[?.!]?\s*$",
        re.I
    ), _h_rates_query, "bid rates / show rates / current rates"),

    # Simple keyword commands
    (re.compile(r"^\s*(?:list\s+bids|active\s+bids|what\s+bids|show\s+bids|bids)\s*[?.!]?\s*$", re.I), _h_list_bids, "list bids"),
    # Route order verified: blockers before compliance (2026-05-17)
    (re.compile(r"^\s*(?:show\s+)?blockers?\s*[?.!]?\s*$", re.I), _h_blockers, "blockers"),
    (re.compile(r"^\s*compliance(?:\s+summary)?\s*[?.!]?\s*$", re.I), _h_compliance, "compliance", 10.0),
    (re.compile(r"^\s*(?:ar\s+aging|aging|receivables\s+aging)\s*[?.!]?\s*$", re.I), _h_ar_aging, "ar aging"),
    (re.compile(r"^\s*shop\s+kpis?\s*[?.!]?\s*$", re.I), _h_shop_kpis, "shop kpis"),
    (re.compile(r"^\s*(?:shop\s+log|production)\s*[?.!]?\s*$", re.I), _h_shop_log, "shop log / production"),
    (re.compile(r"^\s*change\s+orders\s*[?.!]?\s*$", re.I), _h_change_orders, "change orders"),
    (re.compile(r"^\s*houston\s+pipeline\s*[?.!]?\s*$", re.I), _h_houston_pipeline, "houston pipeline"),
    (re.compile(r"^\s*fuel\s+surcharge\s*[?.!]?\s*$", re.I), _h_fuel_surcharge, "fuel surcharge", 10.0),
    (re.compile(r"^\s*self[\s-]*test\s*[?.!]?\s*$", re.I), _h_self_test, "self test", 60.0),
    # v3.2.7.15: VJ scan routes. ORDER MATTERS - more specific first.
    (re.compile(r"^\s*vj\s+result\s+([a-f0-9]{6,12})\s*[?.!]?\s*$", re.I), _h_vj_result, "vj result <job_id>"),
    (re.compile(r"^\s*(?:vj\s+status|scan\s+status|self[\s-]*repair\s+status)\s*[?.!]?\s*$", re.I), _h_vj_status, "vj status"),
    # vj scan and fix [fast] | scan and fix | self repair | self-repair
    # Backend backup if frontend regex shortcut doesn't catch it.
    (re.compile(
        r"^\s*(?:"
            r"(?:vj|virtual\s+joseph)\s+(?:scan\s+and\s+(?:fix|repair)|fix\s+and\s+scan)"
        r"|"
            r"scan\s+and\s+(?:fix|repair)"
        r"|"
            r"self[\s-]*repair"
        r")"
        r"(?:\s+(fast))?\s*[?.!]?\s*$", re.I),
        _h_vj_scan_and_fix, "vj scan and fix / scan and fix / self repair [fast]"),
    # Read-only scan: "vj scan" / "code scan" / "scan codebase" / "run scan"
    (re.compile(
        r"^\s*(?:vj\s+scan|virtual\s+joseph\s+scan|code\s+scan|scan\s+codebase|run\s+scan|run\s+vj)\s*[?.!]?\s*$",
        re.I),
        _h_vj_scan, "vj scan / code scan / scan codebase"),
    (re.compile(r"^\s*(?:morning\s+brief(?:ing)?|daily\s+status|daily\s+brief)\s*[?.!]?\s*$", re.I), _h_morning_brief, "morning brief / daily status"),
    (re.compile(r"^\s*(?:stock\s+brief|brief)\s+([A-Z]{1,5})\s*[?.!]?\s*$", re.I), _h_stock_brief, "stock brief <TICKER>"),
    (re.compile(r"^\s*(?:stock\s+watchlist|watchlist|stocks)\s*[?.!]?\s*$", re.I), _h_stock_watchlist, "stock watchlist"),
    (re.compile(r"^\s*steel\s+prices?\s*[?.!]?\s*$", re.I), _h_steel_prices, "steel prices"),
    (re.compile(r"^\s*(?:market|market\s+dashboard)\s*[?.!]?\s*$", re.I), _h_market, "market dashboard"),
    (re.compile(r"^\s*(?:macro|macro\s+indicators|economy)\s*[?.!]?\s*$", re.I), _h_macro, "macro indicators"),
    (re.compile(r"^\s*(?:whitelist|vendor\s+whitelist|approved\s+vendors)\s*[?.!]?\s*$", re.I), _h_vendor_whitelist, "whitelist / vendor whitelist"),
    (re.compile(r"^\s*(?:quotes?|vendor\s+quotes?|quote\s+log)\s*[?.!]?\s*$", re.I), _h_vendor_quotes, "quotes / vendor quotes"),
    (re.compile(r"^\s*poll\s+vendors?\s*[?.!]?\s*$", re.I), _h_vendor_poll, "poll vendors / request quotes", 15.0),
    (re.compile(r"^\s*emr\s+predict\s*[?.!]?\s*$", re.I), _h_emr_predict, "EMR predict"),
    (re.compile(r"^\s*(?:models?|ai\s+models?|model\s+routing|routing)\s*[?.!]?\s*$", re.I), _h_model_routing, "models / model routing"),
    (re.compile(r"^\s*(?:connectors?|mcp\s+status|mcp\s+http\s+status)\s*[?.!]?\s*$", re.I), _h_mcp_status, "connectors / mcp status"),
    (re.compile(r"^\s*mcp\s+token\s*[?.!]?\s*$", re.I), _h_mcp_token, "mcp token"),
    (re.compile(r"^\s*(?:help|commands|menu|what\s+can\s+you\s+do)\s*[?.!]?\s*$", re.I), _h_help, "help"),
    (re.compile(r"^\s*(?:version|build\s+info)\s*[?.!]?\s*$", re.I), _h_version, "version"),
]


def try_direct_route(bridge, message: str) -> Optional[dict]:
    """Match `message` against direct-route patterns. Return chat response or None.

    Called from `Bridge.ai_ask` BEFORE any AI provider is invoked. If this
    returns a dict, ai_ask returns it directly. If it returns None,
    ai_ask falls through to normal AI handling.
    """
    if not message or not isinstance(message, str):
        return None
    msg = message.strip()
    if not msg:
        return None
    for _route in _ROUTES:
        pattern, handler, _desc = _route[0], _route[1], _route[2]
        _timeout = _route[3] if len(_route) > 3 else 2.0
        m = pattern.match(msg)
        if m:
            _result = [None]
            _exc = [None]
            def _run(_h=handler, _m=m):
                try:
                    _result[0] = _h(bridge, _m)
                except Exception as e:
                    _exc[0] = e
            t = _threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=_timeout)
            if t.is_alive():
                # Handler timed out; fall through to AI
                return None
            if _exc[0] is not None:
                return _fmt_local_response(
                    f"Direct route matched ({_desc}) but handler failed: {type(_exc[0]).__name__}: {_exc[0]}",
                    f"{_desc} (handler error)",
                )
            return _result[0]
    return None


def list_direct_routes() -> list[dict]:
    """Inventory for debugging and the help system."""
    return [
        {"pattern": _r[0].pattern, "description": _r[2]}
        for _r in _ROUTES
    ]


# Compile rate patterns separately so handle_direct works without a bridge object
_RATES_PATTERN = re.compile(
    r"^\s*(?:"
    r"bid\s+rates?|current\s+rates?|fab\s+rates?|erection\s+rates?|"
    r"joist\s+rates?|deck\s+rates?|anchor\s+rates?|"
    r"show\s+(?:me\s+)?rates?|what\s+are\s+(?:the\s+)?(?:bid\s+)?rates?|"
    r"pricing\s+rates?|our\s+rates?"
    r")\s*[?.!]?\s*$",
    re.I
)


_BLOCKERS_PATTERN = re.compile(
    r"^\s*(?:show\s+)?blockers?\s*[?.!]?\s*$",
    re.I
)


def handle_direct(message: str) -> Optional[str]:
    """Bridge-free handler for rate and blockers queries.

    Returns the plain-text response string, or None if the message is not
    a direct-route query. Useful for testing without instantiating the Bridge.
    """
    if not message or not isinstance(message, str):
        return None
    msg = message.strip()
    m = _RATES_PATTERN.match(msg)
    if m:
        result = _h_rates_query(None, m)
        return result.get("text")
    if _BLOCKERS_PATTERN.match(msg):
        return "blockers"
    return None
