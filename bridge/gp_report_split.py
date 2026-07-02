"""
GP REPORT SPLIT - direct vs indirect cost split helper for the -GP
report. Operum-style: indirect costs in a hidden bucket, markup
distributed proportionally across direct line items.

Derived from Operum.io review (2026-05-28). Operum keeps direct costs
client-visible and pushes indirects (G&A, project management,
contingency) into a separate bucket. Sell Price column auto-includes
indirect distribution. For us, the client proposal already hides
indirects inside the per-trade rate (fab $[FAB RATE]/T includes G&A 7.5
percent). That works for client view but obscures the cost structure
on the internal -GP report.

This module produces a separate -GP-only view that:
  - Backs out the implicit 7.5 percent G&A from each direct line
  - Reports direct cost separately
  - Reports indirect cost (G&A + any contingency) separately
  - Recomposes the sell price for cross-check

CRITICAL: This is for the -GP report ONLY. Never include direct/
indirect split on the client proposal PDF. CLAUDE.md hard rule 4
(MATERIAL_COSTS internal only) extends to cost-structure visibility.

Rules:
  - Module-level only.
  - Pure stdlib.
  - _ok / _err for Bridge entry points.
  - Defaults from bridge/bid_rates.py G&A_PCT (7.5%). When this module
    is folded into the live tree, import the rate from bid_rates rather
    than the constant below.
"""

from __future__ import annotations

# Mirror of bid_rates.py G&A_PCT for standalone testing. Replace with
# `from bridge.bid_rates import G_AND_A_PCT` when integrated.
DEFAULT_G_AND_A_PCT = 0.075   # 7.5%
DEFAULT_CONTINGENCY_PCT = 0.0  # we do not carry a separate contingency today


def _ok(payload):
    return {"ok": True, "data": payload}


def _err(message):
    return {"ok": False, "error": message}


def split_line_item(sell_price, g_and_a_pct=DEFAULT_G_AND_A_PCT,
                    contingency_pct=DEFAULT_CONTINGENCY_PCT):
    """Decompose a single sell-price line item into direct + indirect.

    Assumption: the sell_price already has G&A baked in (per
    bid_rates.py model where per-trade rates are gross-of-G&A).
    Reverse the math to back out direct.

    sell_price * (1 + indirect_pct) = sell_price is NOT the model.
    Actual model is: sell_price = direct_cost * (1 + g_and_a_pct).
    So: direct = sell_price / (1 + g_and_a_pct)
        indirect = sell_price - direct

    sell_price: float (positive)
    g_and_a_pct: float (e.g. 0.075 for 7.5%)
    contingency_pct: float (e.g. 0.05 for 5%)

    Returns _ok({direct, g_and_a, contingency, sell_price, check_sum})
    """
    try:
        sp = float(sell_price)
    except (TypeError, ValueError):
        return _err(f"sell_price must be numeric, got {sell_price!r}")
    if sp < 0:
        return _err("sell_price must be >= 0")
    if not (0 <= g_and_a_pct < 1):
        return _err(f"g_and_a_pct must be in [0, 1), got {g_and_a_pct}")
    if not (0 <= contingency_pct < 1):
        return _err(f"contingency_pct must be in [0, 1), got {contingency_pct}")

    total_indirect_pct = g_and_a_pct + contingency_pct
    direct = sp / (1.0 + total_indirect_pct)
    g_and_a = direct * g_and_a_pct
    contingency = direct * contingency_pct
    return _ok({
        "direct": round(direct, 2),
        "g_and_a": round(g_and_a, 2),
        "contingency": round(contingency, 2),
        "sell_price": round(sp, 2),
        "check_sum": round(direct + g_and_a + contingency, 2),
    })


def split_estimate(line_items, g_and_a_pct=DEFAULT_G_AND_A_PCT,
                   contingency_pct=DEFAULT_CONTINGENCY_PCT):
    """Apply split_line_item across a full estimate.

    line_items: list of dicts like:
      [{"description": "Structural steel", "qty": 547, "unit": "T",
        "rate": 4720.0, "sell_price": 2581840.0}, ...]
      sell_price is what we'd quote the client today.

    Returns _ok({...}) with:
      - lines: same list with `direct`, `g_and_a`, `contingency` added
      - totals: {direct_total, g_and_a_total, contingency_total, sell_total}
      - markup_pct: total indirect / total direct
    """
    if not isinstance(line_items, list):
        return _err("line_items must be a list")
    out_lines = []
    direct_total = 0.0
    g_and_a_total = 0.0
    contingency_total = 0.0
    sell_total = 0.0
    for li in line_items:
        sp = li.get("sell_price")
        if sp is None:
            # Try computing from qty * rate
            try:
                sp = float(li.get("qty", 0)) * float(li.get("rate", 0))
            except (TypeError, ValueError):
                sp = 0.0
        result = split_line_item(sp, g_and_a_pct, contingency_pct)
        if not result["ok"]:
            return _err(f"line item {li.get('description', '?')!r}: {result['error']}")
        d = result["data"]
        merged = dict(li)
        merged.update({
            "direct": d["direct"],
            "g_and_a": d["g_and_a"],
            "contingency": d["contingency"],
            "sell_price_computed": d["sell_price"],
        })
        out_lines.append(merged)
        direct_total += d["direct"]
        g_and_a_total += d["g_and_a"]
        contingency_total += d["contingency"]
        sell_total += d["sell_price"]
    markup_pct = 0.0
    if direct_total > 0:
        markup_pct = (g_and_a_total + contingency_total) / direct_total
    return _ok({
        "lines": out_lines,
        "totals": {
            "direct_total": round(direct_total, 2),
            "g_and_a_total": round(g_and_a_total, 2),
            "contingency_total": round(contingency_total, 2),
            "sell_total": round(sell_total, 2),
        },
        "markup_pct": round(markup_pct, 4),
        "g_and_a_pct_input": g_and_a_pct,
        "contingency_pct_input": contingency_pct,
    })


def render_gp_table_markdown(split_payload):
    """Render the direct/indirect split as a -GP report markdown table.

    NEVER include this in the client PDF. The output names indirect
    costs explicitly which the client proposal must not.
    """
    if not isinstance(split_payload, dict) or "lines" not in split_payload:
        return "INVALID_SPLIT_PAYLOAD"
    lines = []
    lines.append("# GP Report - Direct vs Indirect Cost Split")
    lines.append("")
    lines.append("> Internal only. Do NOT include in client proposal PDF.")
    lines.append("")
    lines.append("| Line Item | Qty | Unit | Direct $ | G&A $ | Contingency $ | Sell Price $ |")
    lines.append("|-----------|----:|------|---------:|------:|--------------:|-------------:|")
    for li in split_payload["lines"]:
        desc = str(li.get("description", "")).replace("|", "\\|")
        qty = li.get("qty", "")
        unit = li.get("unit", "")
        d = li.get("direct", 0)
        ga = li.get("g_and_a", 0)
        cont = li.get("contingency", 0)
        sp = li.get("sell_price_computed", 0)
        lines.append(
            f"| {desc} | {qty} | {unit} | "
            f"${d:,.2f} | ${ga:,.2f} | ${cont:,.2f} | ${sp:,.2f} |"
        )
    t = split_payload.get("totals", {})
    lines.append(
        f"| **TOTAL** |  |  | "
        f"**${t.get('direct_total', 0):,.2f}** | "
        f"**${t.get('g_and_a_total', 0):,.2f}** | "
        f"**${t.get('contingency_total', 0):,.2f}** | "
        f"**${t.get('sell_total', 0):,.2f}** |"
    )
    lines.append("")
    lines.append(
        f"Markup pct: {split_payload.get('markup_pct', 0) * 100:.2f}%  "
        f"(G&A input: {split_payload.get('g_and_a_pct_input', 0) * 100:.2f}%, "
        f"Contingency input: {split_payload.get('contingency_pct_input', 0) * 100:.2f}%)"
    )
    return "\n".join(lines)


# Smoke test
if __name__ == "__main__":
    sample = [
        {"description": "Structural steel (columns/beams/girders)",
         "qty": 547, "unit": "T", "rate": 4720.0, "sell_price": 547 * 4720.0},
        {"description": "Joists (K-series)",
         "qty": 280, "unit": "T", "rate": 4500.0, "sell_price": 280 * 4500.0},
        {"description": "Roof deck (Type B, painted)",
         "qty": 231400, "unit": "SF", "rate": 3.70, "sell_price": 231400 * 3.70},
        {"description": "Anchor rods (3/4 in UNO)",
         "qty": 500, "unit": "each", "rate": 75.0, "sell_price": 500 * 75.0},
    ]
    out = split_estimate(sample)
    if not out["ok"]:
        print("ERROR:", out["error"])
    else:
        print(render_gp_table_markdown(out["data"]))
