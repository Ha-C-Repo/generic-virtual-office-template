@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM   OWNER_INSTALL.bat
REM   Run this ONCE on the Owner's Windows machine after extracting the bundle.
REM
REM   What it does:
REM     1. Verifies Python 3.11+ is installed (offers download link if not)
REM     2. Installs all Python dependencies (uses INSTALL_DEPENDENCIES.bat)
REM     3. Creates desktop shortcut
REM     4. Registers Virtual Office as MCP server with Claude Desktop
REM     5. Tests the install end-to-end
REM
REM   After this completes:
REM     - Double-click desktop shortcut to launch Virtual Office GUI
REM     - Use Claude Desktop chat to drive Virtual Office via MCP
REM ═══════════════════════════════════════════════════════════════════════════

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "INSTALL_DIR=%~dp0"
if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

echo.
echo  ╔═══════════════════════════════════════════════════════════════════════╗
echo  ║                                                                       ║
echo  ║      YOUR COMPANY - VIRTUAL OFFICE v3.2.7                           ║
echo  ║      One-time install for The Owner                            ║
echo  ║                                                                       ║
echo  ║      Install dir:                                                    ║
echo  ║      %INSTALL_DIR%
echo  ║                                                                       ║
echo  ╚═══════════════════════════════════════════════════════════════════════╝
echo.
echo  This installer will:
echo    [1] Check Python is installed
echo    [2] Install Python dependencies (~3-5 minutes)
echo    [3] Create desktop shortcut
echo    [4] Register MCP server with Claude Desktop
echo    [5] Run a quick self-test
echo.
pause

REM ─── 1. Python check ───────────────────────────────────────────────
echo.
echo  [1/5] Checking Python installation...
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 --version
    set "PY=py -3"
    goto py_found
)
where python >nul 2>&1
if %errorlevel% equ 0 (
    python --version
    set "PY=python"
    goto py_found
)
echo.
echo  ERROR: Python is not installed.
echo.
echo  Please:
echo    1. Download Python 3.11 or newer from https://www.python.org/downloads/
echo    2. CHECK "Add Python to PATH" during installation
echo    3. Run this installer again
echo.
pause
exit /b 1
:py_found
echo  [ OK ] Python found

REM ─── 2. Install dependencies ────────────────────────────────────────
echo.
echo  [2/5] Installing Python dependencies (~3-5 min)...
echo        Watch for any errors below.
echo.
if exist INSTALL_DEPENDENCIES.bat (
    call INSTALL_DEPENDENCIES.bat
    if %errorlevel% neq 0 (
        echo  WARNING: Dependency install reported errors. See above.
        echo           Continuing - most errors are non-fatal.
    )
) else (
    echo  ERROR: INSTALL_DEPENDENCIES.bat not found in bundle.
    pause
    exit /b 1
)

REM ─── 3. Desktop shortcut ────────────────────────────────────────────
echo.
echo  [3/5] Creating desktop shortcut...
set "EXE=%INSTALL_DIR%\YourCoVirtualOffice.exe"
if not exist "%EXE%" set "EXE=%INSTALL_DIR%\main.py"

set "DESKTOP=%USERPROFILE%\Desktop"
set "LNK=%DESKTOP%\Your Company Virtual Office.lnk"

REM Use PowerShell to create the .lnk
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut('%LNK%'); $s.TargetPath='%EXE%'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.IconLocation='%INSTALL_DIR%\app.ico'; $s.Description='Your Company Virtual Office v3.2.7'; $s.Save()" 2>nul
if exist "%LNK%" (
    echo  [ OK ] Desktop shortcut created
) else (
    echo  [WARN] Could not create desktop shortcut - you can launch from %INSTALL_DIR%
)

REM ─── 4. Claude Desktop MCP registration ─────────────────────────────
echo.
echo  [4/5] Registering with Claude Desktop (MCP integration)...
if exist "%APPDATA%\Claude\claude_desktop_config.json" (
    echo        Found existing Claude Desktop config - will merge our entry.
) else (
    if exist "%APPDATA%\Claude" (
        echo        Claude Desktop installed but no config yet - will create one.
    ) else (
        echo  [SKIP] Claude Desktop not detected in %%APPDATA%%\Claude
        echo         Install Claude Desktop from https://claude.ai/download first,
        echo         then re-run register_with_claude_desktop.bat manually.
        goto skip_mcp
    )
)
call register_with_claude_desktop.bat "%INSTALL_DIR%"
:skip_mcp

REM ─── 5. Self-test ───────────────────────────────────────────────────
echo.
echo  [5/5] Running quick self-test...
%PY% -c "import sys; sys.path.insert(0,r'%INSTALL_DIR%'); from bridge.agents.self_test import run_full_self_test; r=run_full_self_test(); print(f'  Self-test: {r[\"passed\"]}/{r[\"total\"]} ({r[\"health_pct\"]}%%)')"
if %errorlevel% neq 0 (
    echo  [WARN] Self-test could not run - bridge modules may be missing
) else (
    echo  [ OK ] Self-test complete
)

REM ─── Done ───────────────────────────────────────────────────────────
echo.
echo  ╔═══════════════════════════════════════════════════════════════════════╗
echo  ║                                                                       ║
echo  ║      INSTALL COMPLETE                                                ║
echo  ║                                                                       ║
echo  ║  HOW TO USE:                                                          ║
echo  ║                                                                       ║
echo  ║  GUI mode:                                                            ║
echo  ║    Double-click "Your Company Virtual Office" on your desktop           ║
echo  ║                                                                       ║
echo  ║  Claude Desktop / Cowork mode:                                        ║
echo  ║    1. Quit Claude Desktop completely (right-click tray icon)         ║
echo  ║    2. Restart Claude Desktop                                         ║
echo  ║    3. In Claude chat, type:                                          ║
echo  ║       "What can the Your Company Virtual Office do?"                    ║
echo  ║    4. Try: "Run the morning brief from Virtual Office"               ║
echo  ║                                                                       ║
echo  ║  TROUBLESHOOTING:                                                     ║
echo  ║    See SETUP_FOR_OWNER.md in this folder                           ║
echo  ║    Email Joseph: joseph@yourcompany.example.com                              ║
echo  ║                                                                       ║
echo  ╚═══════════════════════════════════════════════════════════════════════╝
echo.
pause
endlocal
