# Your Company Virtual Office - Setup Guide for Owner

**Version 6.1.4 · Houston, TX · Joseph Hasse**

This is the install + integration guide for the Virtual Office desktop app on your Windows machine. It walks you through three things:

1. **Install the desktop app** (5 minutes)
2. **Connect it to your Claude Desktop app** so you can drive it from chat (~2 minutes)
3. **Try the integration** with a couple of example commands

---

## What you're getting

Two tools, one bundle, working in both directions:

**Direction 1 - Standalone GUI**
A desktop app you double-click to open. Lives at `C:\Tools\virtualoffice` (or wherever you unzip). Has the full Virtual Office UI: bid pipeline, AR tracker, change orders, RFIs, Houston refinery outreach, AISC lookup, the morning brief, etc.

**Direction 2 - MCP integration with Claude Desktop**
After install, you can talk to Claude Desktop normally and ask it to do Virtual Office things. Behind the scenes, Claude calls into Virtual Office through a local Model Context Protocol connection. No internet. No cloud sync. Just stdio between Claude Desktop and the EXE.

Examples of what you can ask Claude Desktop after setup:

- "Show me the morning brief from Virtual Office"
- "What's the current W-section steel price per ton?"
- "Look up AISC W14X82 properties"
- "Run the Virtual Office self-test"
- "What are my active priorities?"
- "Compute Houston permit fee for a $2.5M project"
- "Show me change orders for ICD Church"
- "Draft outreach to Marathon Galveston Bay procurement" *(always preview-only - never auto-sends)*

---

## Two clouds, one workflow - how the cost split works

Virtual Office uses **two separate Anthropic accounts on purpose**, and routing work intelligently between them saves money and produces better answers:

| Account | Whose | What it does | Pays for |
|---|---|---|---|
| **Anthropic API** | Joseph's | Virtual Office's autonomous AI engine - bid analysis, document parsing, vision, agent reasoning. Programmatic calls Joseph's key. | Joseph (Your Company business expense) |
| **Claude Desktop** | the Owner's `owner@yourcompany.example.com` subscription | Chat-style work driven by Owner, plus all integrations (Gmail, Calendar, Drive, OneDrive, etc.) routed through MCP | Your existing Claude.ai subscription |

**Why two?** Two reasons:

1. **Cost optimization** - when you ask Claude Desktop to do something Virtual Office could also do, Claude Desktop runs it on your subscription instead of burning Joseph's API credits. Same answer, no API bill.
2. **Better accuracy** - Claude Desktop has direct, authenticated access to *your actual* Gmail, Calendar, Drive, etc. via MCP. When Virtual Office needs to send an email or check a calendar event, it routes through your Claude Desktop's MCP servers - no need for Joseph to maintain his own copies of those credentials.

**The MCP server runs on Joseph's API key infrastructure but processes commands paid for by your subscription** - that's the design. When you type "show me the morning brief" in Claude Desktop, your subscription pays for the chat exchange; Joseph's API key only gets touched if Virtual Office independently needs to do AI work (like analyzing a bid PDF you uploaded).

**Routing rule of thumb:**

- *Autonomous work* (Virtual Office decides on its own to analyze something, draft a doc, or score a bid) -> Joseph's API
- *Chat-driven work* ("Claude, do X for me using Virtual Office") -> your subscription
- *Integration work* (touching Gmail, Calendar, Drive) -> your subscription via MCP - no API call at all

---

## Prerequisites

You need:

- **Windows 10 or 11**
- **Python 3.11 or newer** (download free from [python.org](https://www.python.org/downloads/))
  - During install, **CHECK "Add Python to PATH"** - this is critical
- **Claude Desktop app** (download from [claude.ai/download](https://claude.ai/download))

If you don't have Python or Claude Desktop yet, install them first.

---

## Install - 5 minutes

1. **Unzip the bundle** anywhere. I recommend:
   ```
   C:\Tools\virtualoffice\
   ```
   But your Desktop or Documents folder works too.

2. **Run `OWNER_INSTALL.bat`** (right-click -> "Run as administrator" is safest):
   - Verifies Python is installed
   - Installs all Python dependencies (~3-5 min - coffee break)
   - Creates a desktop shortcut
   - Registers Virtual Office with your Claude Desktop app
   - Runs a quick self-test

   If it pauses with errors, screenshot and email Joseph.

3. **Done.** You'll have:
   - A "Your Company Virtual Office" icon on your Desktop
   - An entry in your Claude Desktop's MCP server list

---

## After install - restart Claude Desktop

Claude Desktop only loads MCP servers at startup, so:

1. **Right-click the Claude Desktop tray icon** (system tray, bottom-right of taskbar)
2. **Click Quit** - fully exit, not just close window
3. **Start Claude Desktop** again from Start Menu

To verify it worked, open Claude Desktop and type:

> What MCP tools are available right now?

You should see Your Company Virtual Office tools listed (about 32 of them).

---

## Try it out

Open Claude Desktop and try these:

### 1. Morning brief
> Run the morning brief from Virtual Office

You should get back: KPIs, priorities, recommended bids, current steel prices, compliance blockers.

### 2. Steel price lookup
> What's the current price per ton for wide-flange A992 steel?

Returns Q2 2026 SteelBenchmarker / Argus / Nucor 90-day average ($1,150/ton typical).

### 3. AISC lookup
> Look up the section properties for W14X82

Returns lb/ft, depth, flange width, web thickness, etc. - pure offline lookup.

### 4. Permit fee
> What would a City of Houston permit cost for a $1.2M project?

Returns $250 base + 0.75% variable = $9,250 total.

### 5. Health check
> Run the Virtual Office self-test

Returns 72/72 passed at 100%.

### 6. Refinery outreach (preview only - safety guarantee)
> Draft outreach to Marathon Galveston Bay procurement contact for Q3 turnaround structural steel

Returns a draft email **for your review**. Even if Claude tries to send it automatically, the MCP server forces `preview_only=True` - outreach can never auto-send via Claude. You confirm in the desktop GUI.

---

## How the two directions actually work

### Claude Desktop -> Virtual Office (the path you'll use most)

```
You type in Claude Desktop chat:
  "Show me the morning brief from Virtual Office"
       ↓
Claude Desktop notices the request matches an MCP tool
       ↓
Spawns: YourCoVirtualOffice.exe --mcp-server
       ↓
Sends JSONRPC over stdin: tools/call get_panel_data
       ↓
Virtual Office's bridge runs the request
       ↓
JSONRPC reply comes back over stdout
       ↓
Claude formats it for you in chat
```

The EXE only runs while the chat is happening - Claude Desktop spawns it on demand.

### Virtual Office -> Claude Desktop's other MCPs

The Virtual Office GUI can also call your existing MCP integrations (Gmail, Calendar, Drive, etc.). It reads `%APPDATA%\Claude\claude_desktop_config.json` to discover them, then spawns the same way. This is exposed via the bridge methods `mcp_list_servers()`, `mcp_list_tools()`, `mcp_call_tool()`.

You'd typically use this for agent workflows that need to send an email or check a calendar event. It's wired but not yet surfaced in the GUI - Joseph adds buttons in the Saturday Session 2 round.

---

## Troubleshooting

### "Claude Desktop doesn't show Virtual Office tools"

1. Did you fully quit Claude Desktop and restart? It only loads MCP servers at startup.
2. Open `%APPDATA%\Claude\claude_desktop_config.json` in Notepad. Look for an entry like:
   ```json
   "your-company-virtual-office": {
     "command": "C:\\Tools\\virtualoffice\\YourCoVirtualOffice.exe",
     "args": ["--mcp-server"]
   }
   ```
   If missing, re-run `register_with_claude_desktop.bat` from the install folder.

### "Python is not installed" when running OWNER_INSTALL.bat

Install Python 3.11+ from python.org. **CHECK** "Add Python to PATH" during install.

### "Some pip install commands failed"

Most are non-fatal. The critical ones are: `pywebview`, `anthropic`, `truststore`, `pdfplumber`. If any of those failed, run from a Command Prompt:

```
py -3 -m pip install pywebview anthropic truststore pdfplumber
```

### "Claude Desktop config got corrupted"

Backup your existing config first:

```
copy "%APPDATA%\Claude\claude_desktop_config.json" "%APPDATA%\Claude\claude_desktop_config.backup.json"
```

Then re-run `register_with_claude_desktop.bat`. The script merges into existing config - it doesn't overwrite.

### "Virtual Office GUI won't open"

Check `%TEMP%\virtualoffice_crash_*.log` for the error. Email it to Joseph.

### "I want to remove the MCP integration but keep the desktop app"

Open `%APPDATA%\Claude\claude_desktop_config.json` in Notepad, delete the `your-company-virtual-office` block (and the trailing comma if needed), save, restart Claude Desktop.

---

## Security notes

- **No network calls** in MCP mode - every tool is local-only.
- **Outreach is preview-only** when called via Claude. Even if Claude tries to set `preview_only=False`, the MCP server forces it back to `True`. The only path that actually sends an outreach is `confirm_refinery_outreach()` from the desktop GUI, which requires your explicit click.
- **API keys** in the install folder under `API Keys/` are **Joseph's keys** (Anthropic, OpenAI, Gemini, FRED) bundled by `BUILD_FOR_OWNER.bat`. They power the autonomous AI engine. Treat that folder like a credential file - don't share it. Joseph rotates them quarterly.
- **Your Claude.ai subscription** (`owner@yourcompany.example.com`) covers the chat-side work via Claude Desktop and the MCP integrations (Gmail, Calendar, Drive). No credentials from your subscription are stored in Virtual Office.
- **Crash logs** go to `%TEMP%\virtualoffice_crash_*.log` and contain stack traces but no API keys or sensitive data.

---

## What gets installed where

| Path | Contents |
|---|---|
| `(install folder)\YourCoVirtualOffice.exe` | The app itself |
| `(install folder)\API Keys\` | Claude / OpenAI / Gemini / FRED API keys |
| `(install folder)\data\calibration_2026Q2.json` | Houston-MSA Q2 2026 market data (sealed via SHA-256) |
| `(install folder)\frontend\` | The chat UI HTML/JS |
| `%APPDATA%\Claude\claude_desktop_config.json` | MCP server registration (merged) |
| `%USERPROFILE%\Desktop\Your Company Virtual Office.lnk` | Desktop shortcut |
| `%TEMP%\virtualoffice_crash_*.log` | Crash logs (created only on errors) |

Nothing modifies the Windows registry.

---

## Reach Joseph

Email: **joseph@yourcompany.example.com**
Phone: (in your contacts under Joseph Hasse)

Saturday afternoon I'll come by to wire up:
- Microsoft 365 / Outlook for `owner@yourcompany.example.com`
- OneDrive bid file ingestion
- Tekla project import

That session takes the install from ~423/500 readiness to ~469/500.

---

*Built 2026-05-08 · Your Company · Houston, TX*
