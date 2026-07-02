@echo off
REM ─────────────────────────────────────────────────────────────────────
REM  Your Company Virtual Office - EXE Watchdog
REM  Phase 2 v3.2.8
REM
REM  Polls every 60 seconds. If VirtualOffice.exe is not running,
REM  relaunches it. Logs all events to data\startup.log.
REM
REM  Run via Task Scheduler (triggered at login, runs indefinitely).
REM  See: schtasks_setup.bat for installation.
REM ─────────────────────────────────────────────────────────────────────

setlocal

cd /d "%~dp0"
set LOG=%~dp0data\startup.log
set EXE=%~dp0dist\VirtualOffice.exe
set PYTHON=py -3.13

if not exist "%~dp0data" mkdir "%~dp0data"

echo [%DATE% %TIME%] watchdog.bat started >> "%LOG%"

:LOOP
REM Check if VirtualOffice.exe is running
tasklist /FI "IMAGENAME eq VirtualOffice.exe" 2>NUL | find /I "VirtualOffice.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    REM Running - check again in 60 seconds
    timeout /t 60 /nobreak >NUL
    goto LOOP
)

REM Check if py main.py is running (dev mode)
tasklist /FI "IMAGENAME eq py.exe" 2>NUL | find /I "py.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    REM Dev mode running - check again in 60 seconds
    timeout /t 60 /nobreak >NUL
    goto LOOP
)

REM Not running - relaunch
echo [%DATE% %TIME%] watchdog: VirtualOffice not running - relaunching >> "%LOG%"
if exist "%EXE%" (
    echo [%DATE% %TIME%] watchdog: starting %EXE% >> "%LOG%"
    start "" "%EXE%"
) else (
    echo [%DATE% %TIME%] watchdog: EXE not found, starting from source >> "%LOG%"
    start "" %PYTHON% "%~dp0main.py"
)

REM Wait before next check to avoid rapid restart loop
timeout /t 30 /nobreak >NUL
goto LOOP
