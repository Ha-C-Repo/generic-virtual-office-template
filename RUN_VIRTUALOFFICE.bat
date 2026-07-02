@echo off
REM ═══════════════════════════════════════════════════════════════
REM  YOUR COMPANY VIRTUAL OFFICE - LAUNCHER
REM  Checks dependencies, then starts the desktop app.
REM ═══════════════════════════════════════════════════════════════

echo  Starting Your Company Virtual Office v3.2.6...

REM ── Quick dependency check ───────────────────────────────────
py -3 -c "import webview, anthropic, openai" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  Dependencies not installed. Running installer first...
    echo.
    call INSTALL_DEPENDENCIES.bat
    if %errorlevel% neq 0 exit /b 1
)

REM ── Launch ───────────────────────────────────────────────────
cd /d "%~dp0"
py -3 main.py
if %errorlevel% neq 0 (
    echo.
    echo  App exited with error. Check the output above.
    echo  Common fixes:
    echo    - Run INSTALL_DEPENDENCIES.bat
    echo    - Check API keys in the "API Keys" folder
    echo    - Try: py -3 main.py  (to see detailed errors)
    echo.
    pause
)
