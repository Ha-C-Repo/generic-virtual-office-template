# Setting up the Your Company Virtual Office as a claude.ai Custom Connector

## What this gets you

Owner chats in the claude.ai web project (or any new chat in this
project workspace). He types "estimate this bid" with a PDF attached.
claude.ai's Claude sees that the Your Company custom connector exposes
84 tools, picks the right one (`run_takeoff`, `compose_full_bid`,
`get_pipeline`, etc.), calls it across the tunnel into the Owner's
Win11 box, and the result comes back into the chat as the reply.

Same brain, two front doors:
- **Desktop chat UI** (forward direction, already works)
- **claude.ai web project** (reverse direction, this setup)

Both call the same `handle_request()` and the same 500+ Bridge
methods. Same accuracy, same data, same files.

---

## One-time setup (~10 minutes)

### Step 1: install Cloudflare Tunnel on the Owner's Win11 box

1. Download `cloudflared-windows-amd64.exe` from
   https://github.com/cloudflare/cloudflared/releases
2. Rename it to `cloudflared.exe`
3. Drop it into `C:\Windows\` (or any folder in PATH)
4. Verify: open a Command Prompt, run `cloudflared --version`. You
   should see a version number.

No Cloudflare account required for ephemeral tunnels (the
`trycloudflare.com` ones). If you want a stable subdomain, sign up
free at cloudflare.com and run `cloudflared tunnel login` once.

### Step 2: start the HTTP MCP server

Two options:

**Option A:** double-click `START_MCP_HTTP.bat` in the install folder.
Leave the window open.

**Option B:** open the desktop chat and type `start mcp http`. The
server runs in a background thread alongside the GUI.

Either way the server is listening on `localhost:7777` and a bearer
token has been written to `API Keys/MCP Token.txt`.

### Step 3: start the Cloudflare Tunnel

In a second Command Prompt window:

```
cloudflared tunnel --url http://localhost:7777
```

cloudflared prints a public HTTPS URL that looks like:

```
https://random-name-1234.trycloudflare.com
```

Leave THIS window open too. Closing it kills the tunnel.

### Step 4: get the bearer token

In the desktop chat, type `mcp token`. You'll see something like:

```
Bearer pYyhK4zFfQo6...   (the full token follows)
```

Copy the full `Bearer <token>` value.

### Step 5: add the connector to claude.ai

1. Open claude.ai in a browser
2. Open your Your Company project
3. Go to **Settings** > **Connectors** (or **Tools**, depending on UI version)
4. Click **Add custom MCP** (or **Add connector**)
5. Fill in:
   - **Name:** `Your Company Office`
   - **URL:** the tunnel URL from Step 3 (e.g. `https://random-name-1234.trycloudflare.com`)
   - **Auth header:** `Authorization: Bearer pYyhK4zFfQo6...` (the full value from Step 4)
6. Save

Within a few seconds the connector lists 84 tools. If it doesn't,
verify the tunnel URL responds to a health check: open it in your
browser, `https://random-name-1234.trycloudflare.com/health` should
return `{"ok": true, "service": "your-company-mcp-http", ...}`.

### Step 6: test in a chat

Start a new chat in the Your Company project on claude.ai. Type:

> What's my bid pipeline?

claude.ai's Claude calls `get_pipeline` through the connector, the
desktop bridge returns the data, and the chat reply summarizes it.

Try also:

> Look up W14X82 properties.
> What's our current compliance status?
> Run a self-test.

---

## Daily use

Once it's set up, both servers stay running:
- HTTP MCP server (background thread in the desktop, or `START_MCP_HTTP.bat`)
- Cloudflare Tunnel (`cloudflared` window)

Owner can chat in either:
- **Desktop app on Win11** for offline-OK, no-cloud-roundtrip work
- **claude.ai web project** for mobile (iPad, phone), or when away
  from the workstation, or when he wants to attach the PDF directly
  into the web chat

Same answers either way.

---

## Stopping it

- `stop mcp http` in the desktop chat shuts down the HTTP server
- Ctrl+C in the cloudflared window kills the tunnel
- Both are independent. Stopping one doesn't stop the other.

---

## Security model

- **Server binds to 127.0.0.1 by default.** Only Cloudflare Tunnel
  (running locally on the same Win11 box) can reach it. Even if
  someone is on the same LAN, they can't hit the server directly.
- **Bearer token required** on every POST. Stored in
  `API Keys/MCP Token.txt`. 32 url-safe bytes (~43 chars).
- **Constant-time token comparison** (no timing side channel).
- **Rate limit:** 60 calls/minute. Lightweight in-process counter,
  fine for one-person use.
- **Token rotation:** type `rotate mcp token` in the desktop chat to
  generate a new token. After rotation, update the claude.ai
  connector's Authorization header with the new value.

The tunnel URL itself is public, but useless without the token.

---

## What about file attachments?

- Text content (emails, scope descriptions, code snippets): pass them
  inline in the chat or as a tool argument. Works the same as a
  desktop chat.
- PDFs and binary files attached in claude.ai: claude.ai uploads them
  to its servers and can extract text/images itself. For tools that
  need the raw bytes (e.g. `run_takeoff` which reads structural PDFs
  with pymupdf4llm), claude.ai's Claude can extract the text and pass
  it as a string argument. For full fidelity, drop the PDF into the
  desktop chat instead.

The 84-tool surface covers the common cases. If a workflow needs
binary attachment passthrough, add it to the tool's `inputSchema`
with a `content_base64` field and decode in the Bridge method.

---

## Troubleshooting

**Health check returns 404 from the browser**
The URL ends with `/health` (or `/`). If you get 404, the path is wrong.

**Connector shows 0 tools**
Server isn't running, OR the tunnel URL doesn't match localhost:7777,
OR the bearer token doesn't match. Confirm with:
1. `mcp http status` in desktop chat - should say running=yes
2. `curl https://your-tunnel-url/health` - should return ok=true
3. Re-copy the token via `mcp token`

**Connector shows tools but calls fail**
Check the bearer token matches. Type `mcp token` and compare to what
you pasted in claude.ai. If they differ, paste the current one.

**"Address already in use" on start**
Another process is using port 7777. Stop it first
(`stop mcp http`) or pick a different port via the Bridge call
`start_mcp_http_server(port=7778)`.

**cloudflared crashes / disconnects**
Free `trycloudflare.com` tunnels can be flaky. For production stability,
register a Cloudflare account and use a named tunnel:
```
cloudflared tunnel login
cloudflared tunnel create your-company
cloudflared tunnel route dns your-company yourco.yourdomain.com
cloudflared tunnel run your-company
```

---

*End of setup guide. File: `SETUP_CLAUDE_AI_CONNECTOR.md`.*
