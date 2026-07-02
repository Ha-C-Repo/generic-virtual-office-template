@echo off
REM ============================================================
REM Set up automatic Gmail engagement scan every 30 minutes
REM ============================================================
REM
REM This registers a Windows Scheduled Task that runs the Gmail
REM engagement scan twice an hour during business hours. Owner
REM stops needing to type `scan gmail` manually - any reply that
REM warrants an engagement record gets proposed automatically.
REM
REM Prerequisites:
REM   1. Gmail MCP must be registered with Claude Desktop
REM      (run register_with_claude_desktop.bat first)
REM   2. Owner must be signed into Gmail in Claude Desktop
REM
REM Usage:
REM   Right-click this file and "Run as administrator"
REM   (the schtasks /create command needs admin rights)
REM
REM To remove later:
REM   schtasks /delete /tn "YourCo_GmailScan" /f
REM ============================================================

setlocal

REM Find this script's directory (project root)
set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%

REM Construct the command - calls the Bridge method directly via
REM a one-liner Python script. Logs go to data\gmail_scan_log.txt
set CMD=py -3 -c "import sys; sys.path.insert(0, r'%ROOT%'); from bridge.api import Bridge; api = Bridge.__new__(Bridge); r = api.scan_recent_gmail_for_engagements(days_back=1, dry_run=False); import json; print(json.dumps(r))"

REM Register the scheduled task to run every 30 minutes, 7AM-7PM weekdays
schtasks /create ^
    /tn "YourCo_GmailScan" ^
    /tr "%CMD% >> \"%ROOT%\data\gmail_scan_log.txt\" 2>&1" ^
    /sc minute ^
    /mo 30 ^
    /st 07:00 ^
    /et 19:00 ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS: Gmail engagement scan now runs every 30 minutes
    echo         between 7AM and 7PM. Output logged to:
    echo         %ROOT%\data\gmail_scan_log.txt
    echo.
    echo To check it ran: type `morning briefing` in the chat window
    echo                  and look for newly-created engagement records.
    echo To remove:       schtasks /delete /tn "YourCo_GmailScan" /f
) else (
    echo.
    echo FAILED: schtasks returned error %errorlevel%.
    echo         Try right-clicking this file and "Run as administrator"
)

endlocal
pause
