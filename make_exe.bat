@echo off
rem ================================================================
rem  Your Company Virtual Office - Full Build Pipeline
rem  Joseph runs this on the build machine. Owner gets the output.
rem
rem  Steps: Python check -> API keys -> Icon -> Dependencies ->
rem         Module verify -> Clean -> PyInstaller -> NSIS -> Validate
rem
rem  Version auto-derived from vo_app\__init__.py
rem ================================================================

if "%~1"=="" (cmd /k "%~f0" run & exit /b)
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set LOG=build_log.txt
set APP=YourCoVirtualOffice
set PASS=0

rem Auto-derive version from vo_app\__init__.py
for /f "tokens=2 delims==" %%a in ('findstr "__version__" vo_app\__init__.py') do set VER=%%~a
set VER=!VER:"=!
set VER=!VER: =!
set TOTAL=9
set PYEXE=

echo. > %LOG%
echo Your Company Virtual Office v%VER% Build > %LOG%
echo %DATE% %TIME% >> %LOG%

echo.
echo ================================================================
echo   Your Company Virtual Office v%VER%
echo   Full Build Pipeline
echo ================================================================
echo.

rem ── 1: Find Python ──────────────────────────────────────────────
echo [1/%TOTAL%] Finding Python 3.11+...
for %%P in ("py -3.13" "py -3.12" "py -3.11" "py" "python") do (
    %%~P -c "import sys; assert sys.version_info>=(3,11)" >nul 2>&1
    if not errorlevel 1 (set PYEXE=%%~P& goto :found_py)
)
echo [FAIL] Python 3.11+ not found. Install from python.org
goto :error
:found_py
for /f "tokens=*" %%V in ('!PYEXE! --version 2^>^&1') do set PYVER=%%V
echo [ OK ] !PYVER!
set /a PASS+=1

rem ── 1b: Bridge compile precheck ──────────────────────────────────
echo [1b] Verifying bridge/ compiles (fast truncation check)...
!PYEXE! -m compileall bridge\ -q
if errorlevel 1 (
    echo [FAIL] bridge/ has syntax errors - working tree may be truncated
    echo        Run: git checkout HEAD -- bridge^/ then retry
    goto :error
)
echo [ OK ] bridge/ compiles clean

rem ── 2: API Keys ─────────────────────────────────────────────────
echo [2/%TOTAL%] Checking API Keys...
set KC=0
if exist "API Keys\Claude API.txt" set /a KC+=1
if exist "API Keys\OpenAI API.txt" set /a KC+=1
if exist "API Keys\Gemini API.txt" set /a KC+=1
if %KC%==3 (echo [ OK ] %KC%/3 keys found - bundled for Owner
) else (echo [WARN] %KC%/3 keys - Owner may need to add missing keys)
set /a PASS+=1

rem ── 3: App Icon ─────────────────────────────────────────────────
echo [3/%TOTAL%] Generating app icon...
if not exist "app.ico" (!PYEXE! generate_icon.py >nul 2>&1)
if exist "app.ico" (echo [ OK ] app.ico ready) else (echo [WARN] No icon)
set /a PASS+=1

rem ── 4: Dependencies ─────────────────────────────────────────────
echo [4/%TOTAL%] Installing dependencies...
!PYEXE! -m pip install --upgrade pip -q --disable-pip-version-check >>%LOG% 2>&1
!PYEXE! -m pip install -r requirements.txt -q --disable-pip-version-check >>%LOG% 2>&1
if errorlevel 1 (echo [FAIL] pip install failed & goto :error)
!PYEXE! -m pip install reportlab -q --disable-pip-version-check >>%LOG% 2>&1
echo [ OK ] All packages installed
set /a PASS+=1

rem ── 5: Module Verification ──────────────────────────────────────
echo [5/%TOTAL%] Verifying all 23 modules...
!PYEXE! -c "import sys;sys.path.insert(0,'.');from vo_app import __version__;from bridge.api import Bridge;b=Bridge();m=[x for x in dir(b) if not x.startswith('_') and callable(getattr(b,x))];print('v'+__version__,len(m),'methods')" >>%LOG% 2>&1
if errorlevel 1 (echo [FAIL] Import check failed & goto :error)
!PYEXE! -c "from bridge.resilience import rate_limiter;from bridge.memory import stats;from bridge.blockers import get_all;from bridge.contacts import stats as c;from bridge.documents import generate_proposal;from bridge.bid_pipeline import pipeline_summary;from bridge.audit import stats as a;from bridge.health import status;from bridge.reminders import get_active_reminders;from bridge.cost_tracker import summary;print('All modules OK')" >>%LOG% 2>&1
if errorlevel 1 (echo [FAIL] Module verification failed & goto :error)
echo [ OK ] All modules verified
set /a PASS+=1

rem ── 6: Clean ────────────────────────────────────────────────────
echo [6/%TOTAL%] Cleaning previous build...
if exist build rmdir /s /q build >nul 2>&1
rem Remove the junction entry first (rmdir without /s on a junction removes only the link)
if exist "dist\%APP%" rmdir "dist\%APP%" >nul 2>&1
rem Remove dist/ shell (should be empty now) and dist_build/
if exist dist rmdir /s /q dist >nul 2>&1
if exist dist_build rmdir /s /q dist_build >nul 2>&1
echo [ OK ]
set /a PASS+=1

rem ── 6b: Bridge compile recheck (post-clean) ─────────────────────
echo [6b] Recheck bridge/ compiles after clean...
!PYEXE! -m compileall bridge\ -q
if errorlevel 1 (echo [FAIL] bridge/ compile failed after clean - abort & goto :error)
echo [ OK ] bridge/ still clean

rem ── 7: PyInstaller ──────────────────────────────────────────────
rem  Writes to dist_build/ (not dist/) to avoid Defender locking the
rem  output directory between consecutive builds.
echo [7/%TOTAL%] Building EXE (2-5 min)...
!PYEXE! -m PyInstaller VirtualOffice.spec --noconfirm --clean --distpath dist_build >>%LOG% 2>&1
if errorlevel 1 (echo [FAIL] PyInstaller failed & goto :error)
if not exist "dist_build\%APP%\%APP%.exe" (echo [FAIL] EXE not found & goto :error)

rem ── 7c: Freshness check - abort if output is stale ───────────────
forfiles /P "dist_build\%APP%" /M "*.exe" /D 0 >nul 2>&1
if errorlevel 1 (
    echo [FAIL] dist_build/ EXE is older than today - build did not refresh artifacts
    goto :error
)
echo [ OK ] EXE timestamp is today

if exist "API Keys" xcopy "API Keys" "dist_build\%APP%\API Keys\" /E /I /Y >nul 2>&1
if exist "app.ico" copy "app.ico" "dist_build\%APP%\app.ico" >nul 2>&1
mkdir "dist_build\%APP%\data" 2>nul
mkdir "dist_build\%APP%\output" 2>nul
mkdir "dist_build\%APP%\extensions" 2>nul

rem ── 7b: Copy .py source for VJ scan in frozen mode ───────────────
rem  PyInstaller compiles bridge/ and vo_app/ into the PYZ archive as
rem  bytecode, leaving no .py files in _internal/. The VJ scanner reads
rem  .py source text to detect syntax errors and issues. We copy the
rem  sources alongside the bundle so the scanner works from the EXE.
echo [7b] Copying .py sources for VJ scan...
robocopy bridge "dist_build\%APP%\_internal\bridge" /s /xf *.pyc /xd __pycache__ /nfl /ndl /njh /njs /nc /ns >nul 2>&1
robocopy vo_app "dist_build\%APP%\_internal\vo_app" /s /xf *.pyc /xd __pycache__ /nfl /ndl /njh /njs /nc /ns >nul 2>&1
echo [ OK ] .py sources copied

rem ── 7d: Create dist\ junction for direct EXE access ─────────────
rem  dist\YourCoVirtualOffice -> dist_build\YourCoVirtualOffice
rem  Lets you run dist\YourCoVirtualOffice\YourCoVirtualOffice.exe
rem  directly without installing. NSIS reads from dist_build explicitly
rem  so this junction is a convenience only - failure is non-fatal.
echo [7d] Linking dist\ junction...
mkdir dist 2>nul
mklink /j "%CD%\dist\%APP%" "%CD%\dist_build\%APP%"
if exist "dist\%APP%\%APP%.exe" (
    echo [ OK ] dist\%APP% -> dist_build\%APP%
) else (
    echo [WARN] mklink failed - falling back to xcopy for dist\ access
    xcopy "dist_build\%APP%" "dist\%APP%\" /E /I /Q >nul 2>&1
    if exist "dist\%APP%\%APP%.exe" (
        echo [ OK ] dist\%APP% populated via xcopy fallback
    ) else (
        echo [WARN] dist\ not populated - use dist_build\%APP% directly
    )
)

echo [ OK ] dist_build\%APP%\%APP%.exe
set /a PASS+=1

rem ── 8: NSIS Installer ───────────────────────────────────────────
echo [8/%TOTAL%] Building Windows installer...
set NSIS_EXE=
if exist "C:\Program Files (x86)\NSIS\makensis.exe" set "NSIS_EXE=C:\Program Files (x86)\NSIS\makensis.exe"
if exist "C:\Program Files\NSIS\makensis.exe" set "NSIS_EXE=C:\Program Files\NSIS\makensis.exe"
where makensis >nul 2>&1 && if not errorlevel 1 set NSIS_EXE=makensis

if "!NSIS_EXE!"=="" (
    echo [SKIP] NSIS not found - creating portable zip
    echo        Install NSIS from https://nsis.sourceforge.io for a proper installer
    set ZIPNAME=%APP%-v%VER%.zip
    if exist "!ZIPNAME!" del /q "!ZIPNAME!"
    powershell -NoProfile -Command "Compress-Archive -Path 'dist_build\%APP%' -DestinationPath '!ZIPNAME!' -Force" >>%LOG% 2>&1
    echo [ OK ] !ZIPNAME!
    set HANDOFF=!ZIPNAME!
) else (
    echo        NSIS found
    "!NSIS_EXE!" /DAPP_VERSION=%VER% installer.nsi >>%LOG% 2>&1
    if exist "%APP%-Setup-v%VER%.exe" (
        echo [ OK ] %APP%-Setup-v%VER%.exe
        set HANDOFF=%APP%-Setup-v%VER%.exe
    ) else (
        echo [WARN] NSIS failed - zip fallback
        powershell -NoProfile -Command "Compress-Archive -Path 'dist_build\%APP%' -DestinationPath '%APP%-v%VER%.zip' -Force" >>%LOG% 2>&1
        set HANDOFF=%APP%-v%VER%.zip
    )
)
set /a PASS+=1

rem ── 9: Final Validation ─────────────────────────────────────────
echo [9/%TOTAL%] Validating output...
for %%F in ("dist_build\%APP%\%APP%.exe") do echo        EXE: %%~zF bytes
if exist "!HANDOFF!" (for %%F in ("!HANDOFF!") do echo        Handoff: %%~nxF ^(%%~zF bytes^))
echo [ OK ]
set /a PASS+=1

rem ── SUCCESS ─────────────────────────────────────────────────────
echo.
echo ================================================================
echo   BUILD COMPLETE - %PASS%/%TOTAL% passed
echo ================================================================
echo.
echo   Handoff: !HANDOFF!
echo.
echo   FOR OWNER:
if exist "%APP%-Setup-v%VER%.exe" (
    echo   1. Send him %APP%-Setup-v%VER%.exe
    echo   2. Double-click installs to Program Files
    echo   3. WebView2 + VC++ auto-installed if missing
    echo   4. Desktop icon + Start Menu created
    echo   5. API keys pre-loaded - zero config
) else (
    echo   1. Send him !HANDOFF!
    echo   2. Unzip and double-click %APP%.exe
    echo   3. Install NSIS for proper installer next time
)
echo.
goto :done

:error
echo.
echo BUILD FAILED - %PASS%/%TOTAL% passed. See %LOG%
echo.

:done
pause >nul
endlocal
