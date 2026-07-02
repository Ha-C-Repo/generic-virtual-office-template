@echo off
REM ─────────────────────────────────────────────────────────────
REM  Your Company Virtual Office - HTTP MCP Server launcher
REM ─────────────────────────────────────────────────────────────
REM  Starts the HTTP MCP server on localhost:7777 so the claude.ai
REM  web project can call Bridge methods through a Cloudflare Tunnel.
REM
REM  Reverse direction (this script):
REM    claude.ai chat -> public tunnel URL -> localhost:7777
REM                                            -> mcp_http_server
REM                                            -> handle_request
REM                                            -> Bridge methods
REM
REM  Forward direction (the GUI):
REM    py -3.13 main.py                       (chat UI calls Bridge)
REM
REM  Both can run simultaneously. The HTTP server is in a background
REM  thread; the GUI runs in its own process if launched separately.
REM ─────────────────────────────────────────────────────────────

cd /d "%~dp0"

echo Starting Your Company MCP HTTP server on localhost:7777 ...
echo.
echo NEXT STEPS:
echo   1. Open a second command window
echo   2. Run: cloudflared tunnel --url http://localhost:7777
echo      (install cloudflared first: https://github.com/cloudflare/cloudflared/releases)
echo   3. Paste the printed https URL into claude.ai project
echo      Settings ^> Connectors ^> Add custom MCP
echo   4. For the auth header, run `mcp token` in the desktop chat
echo      and paste the Bearer value
echo.
echo Press Ctrl+C in this window to stop the server.
echo.

py -3.13 -m bridge.mcp_http_server --port 7777 --host 127.0.0.1
