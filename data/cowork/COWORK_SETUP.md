# Your Company Virtual Office - Cowork MCP Setup Guide
**Admin reference. Joseph Hasse. v3.3.3.**

---

## 1. Local Setup (this machine)

The Virtual Office exposes an MCP server on port 7777 when running.

**Start the MCP server:**

```
py main.py
```

The app starts the MCP endpoint automatically on launch.
Confirm by checking the STATUS tab - should show MCP server active.

**Bearer token location:**

```
C:\Tools\virtualoffice\API Keys\MCP Token.txt
```

Do not share or log this token. Admin reference only.

**Config template location:**

```
C:\Tools\virtualoffice\data\cowork\claude_desktop_config_template.json
```

This template was written to AppData by Joseph during initial setup.
Do not re-deploy unless reinstalling Cowork on a new machine.

---

## 2. Remote Setup (the Owner's machine or new install)

To wire Cowork on another machine:

1. Install Claude Desktop (Cowork).
2. Locate the Claude config file:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Open the config file in a text editor.
4. Add or merge this block under `"mcpServers"`:

```json
{
  "mcpServers": {
    "yourco-virtualoffice": {
      "type": "streamable-http",
      "url": "http://localhost:7777/mcp",
      "headers": { "Authorization": "Bearer <TOKEN>" }
    }
  }
}
```

Replace `<TOKEN>` with the content of `API Keys\MCP Token.txt`.
Do not commit the token to git. Do not paste it in chat.

5. Save the config file.
6. Restart Claude Desktop.

**For remote access (Owner on a different network):**

The Virtual Office must be reachable. Options:
- ngrok tunnel: `ngrok http 7777` - replace `localhost:7777` with the ngrok URL.
- Tailscale: use the Tailscale IP of Joseph's machine instead of `localhost`.
  Update the `url` field to `http://<tailscale-ip>:7777/mcp`.

---

## 3. Verify Connection

After restart, in Claude Desktop (Cowork):

1. Click the hammer icon (tool count should appear - at least 85 tools).
2. Type: "what can I do"
3. Expected response: full command table from the cowork-cheat-sheet skill.

**Current skill count:** 25 (after v3.3.2 Excel patch ships alongside v3.3.3).

If the hammer icon shows 0 tools:
- Confirm `py main.py` is running on the host machine.
- Confirm port 7777 is not blocked by Windows Firewall.
- Check the launch log at `%LOCALAPPDATA%\YourCompany\VirtualOffice\launch.log`.

---

## 4. Troubleshooting

**"Connection refused" on port 7777:**
- Virtual Office is not running. Start it: `py main.py`
- Check if another process is using port 7777: `netstat -an | findstr 7777`

**401 Unauthorized:**
- Token in claude_desktop_config.json does not match `API Keys\MCP Token.txt`.
- Re-read the token file and update the config. Restart Claude Desktop.

**Tool count is wrong (too low):**
- App may have started with import errors. Check `launch.log`.
- Run `py main.py` from a terminal to see startup output.

**Skill not firing:**
- Verify `skills/<skill-name>/SKILL.md` has YAML frontmatter (`---` delimiters).
- Skills without frontmatter are silently skipped by the SkillRegistry.

**Windows Firewall blocking port 7777:**
```
netsh advfirewall firewall add rule name="VirtualOffice MCP" dir=in action=allow protocol=TCP localport=7777
```

---

## 5. Port Reference

| Service | Port | Notes |
|---|---|---|
| MCP server | 7777 | Cowork connects here |
| Frontend dev server | auto-assigned | pywebview internal only |

---

*Token stored at: `C:\Tools\virtualoffice\API Keys\MCP Token.txt`*
*Config template: `C:\Tools\virtualoffice\data\cowork\claude_desktop_config_template.json`*
