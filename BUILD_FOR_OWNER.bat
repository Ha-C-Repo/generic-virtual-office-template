@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM   BUILD_FOR_OWNER.bat
REM   Joseph runs this on his build machine to produce a complete install
REM   bundle for Owner. Combines existing make_exe.bat output with all the
REM   install + Claude Desktop MCP registration scripts into a single ZIP.
REM ═══════════════════════════════════════════════════════════════════════════

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VER=6.1.4"
set "BUNDLE_NAME=YourCo-VirtualOffice-Bundle-v%VER%"
set "BUNDLE_DIR=%~dp0%BUNDLE_NAME%"

echo.
echo  ╔═══════════════════════════════════════════════════════════════════════╗
echo  ║   BUILD FOR OWNER - One-Click Bundle Maker                         ║
echo  ║   Output: %BUNDLE_NAME%.zip
echo  ╚═══════════════════════════════════════════════════════════════════════╝
echo.

REM ─── 1. VACUUM SQLite databases (SIM-01) ──────────────────────────
REM   Reclaim dead-data space before bundling. the Owner's v3.2.7.13
REM   sim found 2.6 MB of bloat shipping in 0-row tables. This step
REM   shrinks them back to schema-only size.
echo  [1/5] VACUUM data\*.db (ship-pipeline cleanup)...
python tools\vacuum_dbs.py data
if %errorlevel% neq 0 (
    echo  WARN: vacuum step failed - continuing anyway
)
echo.

REM ─── 2. Run the existing EXE build pipeline ────────────────────────
echo  [2/5] Running make_exe.bat (PyInstaller + dependency check)...
echo        This creates dist\YourCoVirtualOffice\YourCoVirtualOffice.exe
echo.
call make_exe.bat run
if not exist "dist\YourCoVirtualOffice\YourCoVirtualOffice.exe" (
    echo.
    echo  ERROR: make_exe.bat did not produce the EXE.
    echo         Check build_log.txt for details.
    pause
    exit /b 1
)
echo  [ OK ] EXE built

REM ─── 2. Stage the bundle directory ──────────────────────────────────
echo.
echo  [3/5] Staging bundle directory...
if exist "%BUNDLE_DIR%" rmdir /s /q "%BUNDLE_DIR%" >nul 2>&1
mkdir "%BUNDLE_DIR%"

REM Copy the entire dist folder (EXE + all PyInstaller deps)
xcopy /s /e /i /q "dist\YourCoVirtualOffice\*" "%BUNDLE_DIR%\" >nul
if %errorlevel% neq 0 (
    echo  ERROR: Failed to copy dist contents to bundle.
    pause
    exit /b 1
)

REM Copy install scripts INTO the bundle
copy "OWNER_INSTALL.bat"               "%BUNDLE_DIR%\" >nul
copy "register_with_claude_desktop.bat"  "%BUNDLE_DIR%\" >nul
copy "INSTALL_DEPENDENCIES.bat"          "%BUNDLE_DIR%\" >nul
if exist "SETUP_FOR_OWNER.md"          copy "SETUP_FOR_OWNER.md"  "%BUNDLE_DIR%\" >nul
if exist "STARTUP_PROFILE.md"            copy "STARTUP_PROFILE.md"    "%BUNDLE_DIR%\" >nul
if exist "app.ico"                       copy "app.ico"               "%BUNDLE_DIR%\" >nul

REM API keys (if present, ship them - Owner gets pre-configured)
if exist "API Keys" (
    xcopy /s /e /i /q "API Keys"             "%BUNDLE_DIR%\API Keys\" >nul
    echo  [INFO] Bundled API keys - Owner won't need to add them
)

REM Calibration data (the Q2 2026 source of truth)
if exist "data\calibration_2026Q2.json"  (
    if not exist "%BUNDLE_DIR%\data" mkdir "%BUNDLE_DIR%\data"
    copy "data\calibration_2026Q2.json"  "%BUNDLE_DIR%\data\" >nul
    copy "data\CALIBRATION_HASHES.json"  "%BUNDLE_DIR%\data\" >nul 2>&1
    copy "data\houston_pipeline_seed.json" "%BUNDLE_DIR%\data\" >nul 2>&1
)
echo  [ OK ] Bundle staged

REM ─── 3. Generate the ZIP ────────────────────────────────────────────
echo.
echo  [4/5] Compressing to %BUNDLE_NAME%.zip...
if exist "%BUNDLE_NAME%.zip" del /q "%BUNDLE_NAME%.zip"
powershell -NoProfile -Command "Compress-Archive -Path '%BUNDLE_DIR%' -DestinationPath '%BUNDLE_NAME%.zip' -Force"
if not exist "%BUNDLE_NAME%.zip" (
    echo  ERROR: ZIP creation failed.
    pause
    exit /b 1
)
echo  [ OK ] ZIP created

REM ─── 4. Cleanup + summary ───────────────────────────────────────────
echo.
echo  [5/5] Cleanup...
rmdir /s /q "%BUNDLE_DIR%" >nul 2>&1
for %%F in ("%BUNDLE_NAME%.zip") do echo  Bundle size: %%~zF bytes

echo.
echo  ╔═══════════════════════════════════════════════════════════════════════╗
echo  ║                                                                       ║
echo  ║      BUILD COMPLETE                                                  ║
echo  ║                                                                       ║
echo  ║      Output: %BUNDLE_NAME%.zip
echo  ║                                                                       ║
echo  ║      SEND TO OWNER:                                                 ║
echo  ║      1. Email or share the ZIP file                                  ║
echo  ║      2. Tell him to unzip anywhere (Desktop or C:\Tools both work)   ║
echo  ║      3. Right-click OWNER_INSTALL.bat -^> Run as administrator      ║
echo  ║      4. Wait for self-test confirmation                              ║
echo  ║      5. Restart Claude Desktop                                       ║
echo  ║      6. Test: ask Claude "Run morning brief from Virtual Office"     ║
echo  ║                                                                       ║
echo  ╚═══════════════════════════════════════════════════════════════════════╝
echo.
pause
endlocal
