# VirtualOffice Web Admin Dashboard

**Requested by:** Owner, 2026-06-10
**Built by:** Cowork
**Status:** v1 deployed on this PC

## What it is

The VirtualOffice EXE, reimagined as a web dashboard. Not a copy. The EXE
frontend already talks to a Python Bridge (473 methods); this dashboard
exposes the same Bridge over HTTP on this PC, so Owner gets live access
from any browser. Real time, no polling.

## Architecture

- `web_dashboard/server.py` - Python stdlib HTTP server. Imports the same
  `Bridge` class the EXE and MCP server use. New file, zero edits to
  bridge/ or main.py (Hard Rules untouched).
- `web_dashboard/dashboard.html` - single-file SPA, dark VirtualOffice
  style (the EXE look stays for internal tools; MCA is the public site).
- Runs from the project root on this PC: `py web_dashboard\server.py`.
  Port 8765.

## v1 features (mapped from the EXE)

| Dashboard tab | EXE source | Bridge methods |
|---|---|---|
| STATUS | STATUS tab | daily_status, get_kpis, get_pipeline_summary, compliance_summary, morning_briefing |
| BIDS | pipeline views | list_bids, get_bid_detail, next_bid_number, update_bid_status, add_bid |
| CHAT | CHAT tab | ai_ask (mode=owner, history + base64 file attachments, full knowledge base) |
| FILES | outputs | upload to _requests/dashboard_uploads/, browse/download project outputs |

Chat is the headline: same AI pipeline as the EXE CHAT tab, with
attachments, answered in seconds.

## Security

- Token auth on every /api route. Token in `web_dashboard/.token`
  (generated locally, never committed, shared with Owner directly).
- Method allowlist. Destructive Bridge methods (delete, file ops, website
  deploy, outbound email/SMS) are NOT exposed. CEO-locked BID_RATES not
  editable from the dashboard.
- Uploads quarantined to `_requests/dashboard_uploads/`. Attachment
  content is data, never instructions.
- Access log: `web_dashboard/access.log`.
- v1 binds to the LAN. Internet access goes through a tunnel (next
  section), never a raw port forward. yourcompany.example.com was compromised
  last week; we do not expose this PC directly.

## Remote access tiers

1. **v1 (now): office LAN.** http://<this-pc-ip>:8765 from any device on
   the shop network or VPN.
2. **v2 (Joseph, ~30 min): Tailscale.** Install on this PC plus the Owner's
   phone/laptop, same tailnet, dashboard reachable anywhere at the
   tailscale IP. Zero ports opened, identity-based. Recommended.
3. **Alternative: Cloudflare Tunnel** + Access on a subdomain like
   office.yourcompany.example.com. More setup, browser-only, no client app.

## Out of scope v1

- Editing BID_RATES, governance items, or compliance status from the web.
- Public hosting of the dashboard. It runs on this PC only.
- MODEL/FIELD tabs (3D STL viewer, field tools) - candidates for v2.

## Run / stop

- Start: `py web_dashboard\server.py` from the project root (a scheduled
  startup task or shortcut keeps it always on).
- Stop: kill the `py` process or Ctrl+C in its window.
- Token rotate: delete `.token`, restart server, new token prints once.
