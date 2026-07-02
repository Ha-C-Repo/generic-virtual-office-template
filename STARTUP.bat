@echo off
REM ─────────────────────────────────────────────────────────────────────
REM  Your Company Virtual Office - Dependency-Ordered Launch
REM  Phase 2 v3.2.8
REM
REM  Launch order:
REM    1. VirtualOffice.exe (or py main.py in dev mode)
REM    2. Wait 30 seconds for app to initialize
REM    3. MCP HTTP server (port 7777)
REM    4. Cloudflare Tunnel (if cloudflared.exe found)
REM
REM  Cowork is launched automatically by VirtualOffice.exe (Phase 1).
REM  This script handles the service layer.
REM
REM  Startup log: %~dp0data\startup.log
REM ─────────────────────────────────────────────────────────────────────

setlocal

cd /d "%~dp0"
set LOG=%~dp0data\startup.log
set EXE=%~dp0dist\VirtualOffice.exe
set PYTHON=py -3.13

REM Ensure data\ exists for log
if not exist "%~dp0data" mkdir "%~dp0data"

echo [%DATE% %TIME%] STARTUP.bat launched >> "%LOG%"

REM ── Step 1: Launch VirtualOffice.exe ─────────────────────────────────
echo [%DATE% %TIME%] Step 1: checking VirtualOffice... >> "%LOG%"
tasklist /FI "IMAGENAME eq VirtualOffice.exe" 2>NUL | find /I "VirtualOffice.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] VirtualOffice.exe already running - skip >> "%LOG%"
    echo VirtualOffice.exe already running.
) else (
    if exist "%EXE%" (
        echo [%DATE% %TIME%] Starting %EXE% >> "%LOG%"
        echo Starting VirtualOffice.exe...
        start "" "%EXE%"
    ) else (
        echo [%DATE% %TIME%] EXE not found, starting from source >> "%LOG%"
        echo Starting VirtualOffice from source...
        start "" %PYTHON% "%~dp0main.py"
    )
)

REM ── Step 2: Wait for app to initialize ───────────────────────────────
echo [%DATE% %TIME%] Step 2: waiting 30s for app to initialize... >> "%LOG%"
echo Waiting 30 seconds for app to initialize...
timeout /t 30 /nobreak >NUL

REM ── Step 3: Launch MCP HTTP server ───────────────────────────────────
echo [%DATE% %TIME%] Step 3: checking MCP HTTP server... >> "%LOG%"
netstat -an | find "7777" | find "LISTENING" >NUL
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] MCP HTTP server already running on port 7777 - skip >> "%LOG%"
    echo MCP HTTP server already running.
) else (
    echo [%DATE% %TIME%] Starting MCP HTTP server >> "%LOG%"
    echo Starting MCP HTTP server on port 7777...
    start "" /MIN %PYTHON% -m bridge.mcp_http_server --port 7777 --host 127.0.0.1
    timeout /t 5 /nobreak >NUL
    echo [%DATE% %TIME%] MCP HTTP server started >> "%LOG%"
)

REM ── Step 4: Launch Cloudflare Tunnel ─────────────────────────────────
echo [%DATE% %TIME%] Step 4: checking Cloudflare Tunnel... >> "%LOG%"
tasklist /FI "IMAGENAME eq cloudflared.exe" 2>NUL | find /I "cloudflared.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] cloudflared already running - skip >> "%LOG%"
    echo Cloudflare Tunnel already running.
) else (
    where cloudflared >NUL 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [%DATE% %TIME%] Starting Cloudflare Tunnel >> "%LOG%"
        echo Starting Cloudflare Tunnel...
        start "" /MIN cloudflared tunnel --url http://localhost:7777
        echo [%DATE% %TIME%] cloudflared started >> "%LOG%"
    ) else (
        echo [%DATE% %TIME%] cloudflared not found - tunnel skipped >> "%LOG%"
        echo Cloudflare Tunnel: cloudflared.exe not found. Skipping.
        echo   To enable: download cloudflared-windows-amd64.exe from
        echo   https://github.com/cloudflare/cloudflared/releases
        echo   Rename to cloudflared.exe and add to PATH or C:\Windows\
    )
)

echo [%DATE% %TIME%] STARTUP.bat complete >> "%LOG%"
echo.
echo Startup complete. Check %LOG% for details.
endlocal
