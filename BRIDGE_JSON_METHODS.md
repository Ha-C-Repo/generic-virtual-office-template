# Bridge JSON-Method Reference Card

**Build:** v3.2.7. **Generated:** 2026-05-13.

Bridge has **32 methods that take JSON string arguments** instead of
plain dicts. This is because the pywebview bridge serializes JS objects
to JSON anyway, so passing the JSON string directly avoids a round-trip.

For chat-based or scripted use, **you have to build the JSON yourself**.
Common chat shortcuts in `frontend/app.js` already do this for the
top patterns. This card documents what each method expects so you can
call them from the dev console, scripts, or future chat aliases.

> **Parameter order matters.** A few methods don't put the JSON arg
> first (the Owner's footgun spotted in pass 5). When the signature
> mixes plain args and JSON args, the order in the header below is
> the **real** order from `inspect.signature(Bridge.method)`. Use
> keyword args (`method(plates_json=..., verified_tons=...)`) to
> avoid positional confusion.

---

## Calling convention

All JSON args are passed as **strings** (the literal text of the JSON),
not as objects. From Python:

```python
import json
members = [{"shape": "W14X82", "length_ft": 20, "qty": 4}]
result = bridge.generate_3d_model(members_json=json.dumps(members))
```

From JS:

```javascript
const members = [{shape: "W14X82", length_ft: 20, qty: 4}];
const result = await window.bridge.generate_3d_model(JSON.stringify(members));
```

Every method returns `{ok, data, error}` (post-Fix H).

---

## Categories

1. [Takeoff & member data](#1-takeoff--member-data)
2. [3D model & DXF generation](#2-3d-model--dxf-generation)
3. [Connection analysis](#3-connection-analysis)
4. [ERP & export integrations](#4-erp--export-integrations)
5. [Estimating & engagement](#5-estimating--engagement)
6. [QC & shop floor](#6-qc--shop-floor)
7. [Logistics](#7-logistics)
8. [Misc steel & rendering](#8-misc-steel--rendering)

---

## 1. Takeoff & member data

### `members_json` shape (used by 15+ methods)

The most common JSON shape across Bridge. Frontend stores this as
`window._lastTakeoffMembers` after auto_process_drawing finishes.

```json
[
  {
    "mark":      "B1",
    "shape":     "W14X82",
    "size":      "W14X82",
    "length_in": 240,
    "length_ft": 20,
    "qty":       4,
    "grade":     "A992",
    "sequence":  1,
    "lot":       "A",
    "camber":    0,
    "bbox":      [120.0, 480.0, 380.0, 510.0],
    "x_ft":      0, "y_ft": 0, "z_ft": 0
  }
]
```

Required fields vary by method (see each below). The optional fields
(`bbox`, `grade`, `camber`, etc.) are filled in when present.

---

### `compare_grades(members_json, grades_json="", price_overrides_json="")`

Compare material cost across A992, A572 Gr50, A588, A36 etc.

**`members_json`**: array of `{shape, length_ft, qty}`. Other fields ignored.
**`grades_json`** (optional): array of grade names e.g. `["A572_Gr50","A588"]`.
Default: all common structural grades.
**`price_overrides_json`** (optional): `{"A992": 0.85, "A572_Gr50": 0.92}` USD/lb.

```python
b.compare_grades(
  members_json='[{"shape":"W14X82","length_ft":20,"qty":4}]',
  grades_json='["A572_Gr50","A588"]'
)
```

Returns `{ok, data: {current_grade, current_cost, options:[{grade, cost, savings_vs_current, savings_pct}], best_savings}}`.

---

### `recommend_erection_order(members_json)`

Recommend erection sequence (columns first, then beams).

**`members_json`**: array of `{mark, shape, qty}` — `shape` starting with
`HSS` or `W14` is treated as columnar; `W18`+ as beam.

---

### `index_project(bid_number, project_name, takeoff_result_json, client, location)`

Index a completed takeoff into project memory.

**`takeoff_result_json`**: full result dict from `auto_process_drawing`,
serialized. Includes `members`, `summary`, `total_tons`.

---

### `backtest_project(manual_members_json, ai_members_json, manual_tons, ai_tons, bid_number, project_name)`

Shadow backtest: compare AI vs manual takeoff.

Both `_json` args are the same `members_json` shape. Plus `manual_tons`
and `ai_tons` as floats.

---

## 2. 3D model & DXF generation

### `generate_3d_model(members_json)`

Generate STL from JSON members.

**`members_json`**: array of `{shape, length_ft, x_ft, y_ft, z_ft, mark}`.
The `x_ft, y_ft, z_ft` are optional (default 0).

```python
b.generate_3d_model('[{"shape":"W14X82","length_ft":20,"x_ft":0,"y_ft":0,"z_ft":0,"mark":"C1"}]')
```

Note: there is also `generate_3d_view(shape, length_ft, qty)` which is the
simpler signature for single-member viewing — use that for chat shortcuts.

---

### `generate_part_dxf(member_json)`

1:1 DXF part drawing for a single member.

**`member_json`** (singular, not plural): a single member dict, not an array.

```python
b.generate_part_dxf('{"shape":"W14X82","length_in":240,"mark":"B1"}')
```

---

### `generate_dstv(member_json)`

DSTV/NC1 file for robotic beam lines.

Same `member_json` shape as `generate_part_dxf`. Adds hole and cope data
if present: `holes: [{x, y, dia}]`, `copes: [{end, depth, length}]`.

---

### `generate_gcode_piranha(member_json, thickness_in)`

G-code (.nc) for Piranha plasma table.

**`member_json`**: single member dict.
**`thickness_in`**: plate thickness in inches (float).

---

### `generate_punch_map(member_json)`

Punch map PDF for shop floor posting.

---

### `generate_dxf(shape, members_json, holes_json, output_type)`

General-purpose DXF generator.

**`members_json`**: array of member dicts.
**`holes_json`** (optional): `[{x, y, dia}]` array.
**`output_type`**: one of `cross_section`, `plan`, `holes`, `cope`.

---

### `generate_gcode(data_json, gcode_type)`

General-purpose G-code generator.

**`gcode_type`**: `"drill"` or `"plasma"`.
**`data_json`**: depends on type:
  - `drill`: `{member, holes: [{x, y, dia}]}`
  - `plasma`: `{shape, length, thickness, cuts: [{start, end, kerf}]}`

---

### `generate_ironworker(data_json, program_type)`

Ironworker program (Geka/Sunrise style).

**`program_type`**: `"punch"`, `"shear"`, or `"cope"`.
**`data_json`**: shape depends on type. Always includes `member` and the
relevant operation list.

---

### `generate_stop_list(members_json)`

Stop-list CSV for Geka/Sunrise back gauges.

**`members_json`**: array of `{shape, length_in, qty, mark}`.

---

### `generate_calc_pack(takeoff_result_json, bid_number, project_name)`

PE-friendly Excel calc pack from takeoff data.

**`takeoff_result_json`**: full takeoff result (same as `index_project`).

---

## 3. Connection analysis

### `analyze_connection_details(members_json, pdf_path, page_num)`

Find connection nodes and analyze details (Gemini Vision when available,
geometry fallback otherwise).

**`members_json`**: array of member dicts with `bbox: [x0, y0, x1, y1]`
required.

```python
members = [
  {"mark": "B1", "shape": "W14X82", "bbox": [120, 480, 380, 510]},
  {"mark": "C1", "shape": "HSS6X6X1/4", "bbox": [120, 480, 140, 800]}
]
b.analyze_connection_details(json.dumps(members), pdf_path="/path/to.pdf", page_num=0)
```

Returns `{ok, data: {nodes_found, nodes_analyzed, nodes:[...], summary}}`.

---

### `compute_assembly_costs(details_json)`

Connection hardware costs from detail_vision output.

**`details_json`**: array of detail dicts. Each needs `connection_type`.
Optional: `moment`, `bolt_count`, `cope_required`.

```json
[
  {"connection_type": "shear_tab", "bolt_count": 4},
  {"connection_type": "moment_plate", "moment": true, "bolt_count": 6}
]
```

---

### `estimate_connection_weight(details_json, structural_tons)`

Estimate connection hardware weight from detail vision output.

**`details_json`**: same shape as `compute_assembly_costs`.
**`structural_tons`**: total structural tonnage as float.

---

### `cross_verify(results_json)`

Compare member extractions from multiple AI providers.

**`results_json`**: array of provider results.

```json
[
  {"provider": "gemini", "members": [...]},
  {"provider": "openai", "members": [...]},
  {"provider": "claude", "members": [...]}
]
```

---

### `generate_rfi_log(members_json, cross_verify_json, project_name, bid_number)`

Detect missing info and generate RFI questions.

**`members_json`**: standard member array.
**`cross_verify_json`** (optional): output from `cross_verify` above.

---

## 4. ERP & export integrations

### `export_tekla_xml(bid_number, project_name, members_json)`

Export takeoff data as Tekla PowerFab XML.

Frontend reads `window._lastTakeoffMembers` after auto_process_drawing
and passes the JSON string here. Each member must carry:
- `mark`, `qty`, `shape`, `size`, `length_in` **(required)**
- `grade`, `sequence`, `lot`, `camber` *(optional)*

---

### `export_strumis_xml(bid_number, project_name, members_json)`

Same shape as `export_tekla_xml`. Mirrors that handler.

---

### `export_misc_steel_to_tekla(bid_number, project_name, misc_rollup_json)`

Export AISC-valid misc items via the Tekla XML pipeline.

**`misc_rollup_json`**: shape returned by `detect_misc_steel`, which is:

```json
{
  "railings":  {"items": [...], "total_lbs": 0},
  "stairs":    {"items": [...], "total_lbs": 0},
  "lintels":   {"items": [...], "total_lbs": 0},
  "plates":    {"items": [...], "total_lbs": 0},
  "total_weight_lbs": 0,
  "total_tons": 0
}
```

---

## 5. Estimating & engagement

### `vm_evaluate(bid_info_json)`

Evaluate a single bid against the Owner's preferences.

**`bid_info_json`**: bid dict with at minimum
`{name, client, location, est_tons, due_date}`.

---

### `vm_start_estimating(bid_info_json)`

Create project folder and start estimating workflow. Same shape as
`vm_evaluate`.

---

### `scan_engagements_from_messages(messages_json, dry_run)`

Scan a batch of email message dicts and propose engagement records.

**`messages_json`**: array of message dicts:

```json
[
  {"from": "x@y.com", "subject": "...", "body": "...", "date": "2026-05-13"}
]
```

**`dry_run`** (bool): if true, returns proposals without writing.

---

### `save_channel_config(config_json)`

Save external channel config.

**`config_json`**: channel dict, shape varies by channel type:

```json
{
  "channel": "gmail",
  "address": "ops@yourcompany.example.com",
  "polling_minutes": 15
}
```

---

## 6. QC & shop floor

### `verify_photo_qc(photo_path, expected_holes_json)`

Verify fabrication photo against CNC hole coordinates.

**`expected_holes_json`**: `[{x, y, dia}]` from the CNC program.
**`photo_path`**: path to JPG/PNG photo of the fabricated piece.

---

## 7. Logistics

### `plan_truck_loads(pieces_json, truck_capacity_lbs)`

Plan truck loads by weight and erection sequence.

**`pieces_json`**: array of `{mark, weight_lbs, sequence}`.
**`truck_capacity_lbs`**: float, default 48000.

---

## 8. Misc steel & rendering

### `estimate_misc_steel(verified_tons, member_count, building_type, plates_json)`

Estimate misc steel (connections, plates, hardware) as % of tonnage.

**`plates_json`**: array of `{name, qty, weight_lbs}` for explicit plates.
**`building_type`**: `"warehouse"`, `"office"`, `"refinery"`, etc.

---

### `render_tagged_pdf(source_pdf, members_json, summary_json, output_path, force_ai)`

Annotate a drawing PDF with color-coded shape tags.

**`members_json`**: standard member array (must have `bbox` for placement).
**`summary_json`**: summary dict with `total_tons`, `member_count`.
**`source_pdf`**: input path.
**`output_path`**: output path.
**`force_ai`**: bool, force Gemini/OpenAI even for text PDFs.

---

### `run_value_engineering(members_json, connections_json, base_bid_usd, project_name)`

Generate a VE proposal with section and bolt optimization.

**`members_json`**: standard member array.
**`connections_json`**: array of `{type, bolt_count, moment}` (same shape
as `compute_assembly_costs` input).
**`base_bid_usd`**: float, the base bid for ROI calc.

---

## 9. Workbench

### `get_workbench_data(project_id, members_json)`

Get annotated member data for the workbench overlay.

**`members_json`**: standard member array.

---

## Convention summary

| Suffix | Shape |
|---|---|
| `members_json` | Array of member dicts: `{mark, shape, length_in, qty, ...}` |
| `member_json` | Single member dict (no array) |
| `details_json` | Array of connection detail dicts: `{connection_type, bolt_count, ...}` |
| `data_json` | Method-specific shape (see method) |
| `config_json` | Single config dict |
| `bid_info_json` | Single bid dict |
| `holes_json` | Array of `{x, y, dia}` |
| `messages_json` | Array of email message dicts |
| `pieces_json` | Array of `{mark, weight_lbs, sequence}` |
| `plates_json` | Array of `{name, qty, weight_lbs}` |
| `misc_rollup_json` | Categorized misc-steel dict (railings/stairs/lintels/plates) |
| `takeoff_result_json` | Full auto_process_drawing result |
| `results_json` | Array of provider result dicts |
| `summary_json` | Takeoff summary dict `{total_tons, member_count}` |

---

## Chat-shortcut translation

For chat-based use, here are the natural-language patterns that
already route to JSON methods via `frontend/app.js`:

| You type | Routes to |
|---|---|
| `3d model of W14X82 at 20 feet` | `generate_3d_view` (simpler sig, no JSON) |
| `compare grades for {members}` | `compare_grades` (needs JSON arg) |
| `export tekla for project X` | `export_tekla_xml` with `window._lastTakeoffMembers` |
| `export strumis for project X` | `export_strumis_xml` with `window._lastTakeoffMembers` |
| `value engineering on this bid` | `run_value_engineering` (needs JSON args) |

The methods marked "needs JSON arg" are the ones that don't have a chat
shortcut yet. Use the console / API for those, or wire a shortcut in
`app.js` if used frequently.

---

## Pass 7 addition: vendor quote poller (no JSON args, all string)

Six new methods. None take JSON-string args, so they call cleanly from
the dev console.

| Method | Signature | What it returns |
|---|---|---|
| `poll_vendor_mailbox(force=False)` | bool force | `{polled, recorded[], skipped, whitelist_size}` |
| `get_vendor_quotes(vendor, project, days=30, status)` | optional filters | `{count, quotes[], filters}` |
| `get_vendor_whitelist()` | — | `{count, whitelist[]}` |
| `add_vendor_to_whitelist(domain, vendor_name, vendor_type, notes)` | strings | `{added, domain, entry}` |
| `vendor_poller_status()` | — | snapshot dict |
| `record_vendor_quote(sender_email, subject, body, received_at, attachments_json, message_id)` | strings + optional JSON | `{recorded, doc_number, vendor, project_ref}` |

Chat shortcuts:

| You type | Routes to |
|---|---|
| `quotes` / `vendor quotes` / `recent quotes` | `get_vendor_quotes(days=30)` |
| `poll vendors` / `check for new quotes` | `poll_vendor_mailbox(false)` |
| `whitelist` / `vendor whitelist` / `vendors` | `get_vendor_whitelist()` |
| `add vendor <domain>` | `add_vendor_to_whitelist(domain)` |
| `poller status` / `vendor status` | `vendor_poller_status()` |

Document numbering: every recorded quote gets `NC-{YYYY}-VQ-{NNN}`.
State files (data fabric): `data/vendor_quotes.json`,
`data/vendor_whitelist.json`, `data/vendor_poller_state.json`.
Saved attachments: `data/vendor_quote_attachments/`.

---

## Pass 8 addition: AI model router + remote MCP connectors

Eight new methods. None require JSON-string args. Lets Owner route
specific tasks to Opus 4.7 / 4.6 when accuracy matters more than cost,
and lets the Bridge attach Claude Desktop App-equivalent remote MCP
connectors to API calls.

| Method | Signature | What it returns |
|---|---|---|
| `get_model_routing()` | — | full tier/model/task map |
| `set_model_routing(task_type, tier)` | strings | `{ok, task_type, tier, model}` |
| `clear_model_routing(task_type="")` | optional string | `{ok, cleared, ...}` (empty=all) |
| `escalate_to_opus(prompt, system, tier="max", max_tokens=2000)` | strings | `{model, tier, text, tokens}` |
| `list_remote_mcps()` | — | `{servers[], total, enabled, names}` |
| `add_remote_mcp(name, url, description, categories_csv)` | strings | `{added, entry}` |
| `remove_remote_mcp(name)` | string | `{removed, name, remaining}` |
| `call_with_mcps(prompt, mcp_names_csv, category, tier, system, max_tokens)` | strings | `{model, text, mcp_tool_uses[], mcp_tool_results[]}` |

Tier registry (in `bridge/ai_model_router.py`):

| Tier | Model | Best for |
|---|---|---|
| `fast` | claude-haiku-4-5-20251001 | chat replies, classification, summary |
| `default` | claude-sonnet-4-6 | drafting, takeoff, voice, bid strategy |
| `accurate` | claude-opus-4-6 | complex compliance, code review |
| `max` | claude-opus-4-7 | max-accuracy bid analysis, high-stakes calls |

Chat shortcuts:

| You type | Routes to |
|---|---|
| `models` / `model status` | `get_model_routing()` |
| `use opus for compliance` | `set_model_routing('compliance', 'max')` |
| `use sonnet for bid_strategy` | `set_model_routing('bid_strategy', 'default')` |
| `escalate to opus: <prompt>` | `escalate_to_opus(prompt)` |
| `reset model routing` | `clear_model_routing('')` |
| `connectors` / `remote mcps` | `list_remote_mcps()` |
| `add connector <name> <url>` | `add_remote_mcp(name, url)` |
| `remove connector <name>` | `remove_remote_mcp(name)` |
| `call with mcps <names>: <prompt>` | `call_with_mcps(prompt, names)` |

State files (data fabric): `data/model_routing.json`,
`data/remote_mcps.json`.

How "use the Owner's Claude Desktop App" actually works (architectural note):

1. **Stdio MCPs** (command+args in `claude_desktop_config.json`) -> handled
   by `bridge/mcp_client.py` since pass 6. Subprocess-spawn pattern.
2. **Remote URL MCPs** (Settings > Connectors in Claude Desktop) ->
   handled by `bridge/mcp_remote.py` in pass 8. The Bridge maintains a
   curated registry and attaches matching URLs to outbound Anthropic API
   calls via the `mcp_servers` parameter. Claude (via API) then has
   access to the same remote services Owner sees in his Desktop App.
3. **Opus 4.7 / 4.6 access** -> via the same Anthropic API key, just
   passing the new model_id string. Tier system in
   `bridge/ai_model_router.py` makes the routing decision explicit and
   overridable per task type.

---

## Pass 9 addition: HTTP MCP transport (reverse direction)

Lets the claude.ai web project call INTO the desktop software's Bridge
methods through a Cloudflare Tunnel. Same 84-tool surface as the stdio
path used by Claude Desktop App. Token-authenticated, rate-limited,
binds 127.0.0.1 by default.

Architecture:
```
Forward (existing, pass 6-8):
  Desktop GUI / Desktop App → Bridge → Anthropic API + remote MCPs

Reverse (pass 9):
  claude.ai project chat → Cloudflare Tunnel → localhost:7777
                          → mcp_http_server.py → handle_request()
                          → same Bridge methods → result back to chat
```

Both routes hit the same Bridge. Same accuracy, same data, same files.
Use desktop chat when offline-tolerant; use claude.ai when mobile or
attaching a PDF in the browser.

### `start_mcp_http_server(port=7777, host="127.0.0.1")`
Boots the HTTP MCP server in a background thread. Default 127.0.0.1
so only Cloudflare Tunnel (running locally) can reach it. Auto-loads
or generates bearer token. Returns `{started, url_local, health,
token_fingerprint, next_step}`.

### `stop_mcp_http_server()`
Clean shutdown of the HTTP server. Returns `{stopped, reason}`.

### `mcp_http_server_status()`
Snapshot of running state. Returns `{running, host, port, url_local,
thread_alive, token_file, recent_call_count}`.

### `get_mcp_token()`
Returns the bearer token for claude.ai connector config:
`{token, fingerprint, header_value: "Bearer <tok>", next_step}`.

### `rotate_mcp_token()`
Generates a new token. Invalidates the existing claude.ai connector.
Returns `{token, fingerprint, warning}`.

Chat shortcuts (all string-only, no JSON):
- `start mcp http` / `start mcp server` / `expose mcp`
- `stop mcp http` / `unexpose mcp`
- `mcp http status` / `mcp server status` / `mcp server`
- `mcp token` / `show mcp token` / `get mcp token`
- `rotate mcp token` / `new mcp token`

Operational note: file `API Keys/MCP Token.txt` is generated on first
launch and is excluded from the shipped zip — Joseph regenerates it
locally and feeds the value to the Owner's claude.ai connector config
manually. Setup walkthrough: `SETUP_CLAUDE_AI_CONNECTOR.md`. Launcher:
`START_MCP_HTTP.bat`.

---

*End of reference card. File: `BRIDGE_JSON_METHODS.md`.*
