@echo off
REM Installs the software the clone left missing, using the official
REM winget repository. Right-click this file > Run as administrator.
REM (Running elevated avoids the separate admin prompt that failed before.)

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Please right-click this file and choose "Run as administrator".
  pause
  exit /b
)

echo ============================================================
echo  Installing Epic Games Launcher (required to install Unreal
echo  Engine). After it installs, open it, sign in to your Epic
echo  account, and install Unreal Engine 5.8 from the launcher.
echo ============================================================
winget install --id EpicGames.EpicGamesLauncher -e --accept-source-agreements --accept-package-agreements

echo.
echo ============================================================
echo  Installing NSIS (Nullsoft installer builder)...
echo ============================================================
winget install --id NSIS.NSIS -e --accept-source-agreements --accept-package-agreements

echo.
echo ============================================================
echo  Trying PDFgear (may fail - vendor download is currently
echo  returning 403; if so, install it manually from pdfgear.com).
echo ============================================================
winget source update >nul 2>&1
winget install --id PDFgear.PDFgear -e --accept-source-agreements --accept-package-agreements

echo.
echo Done. See notes from Claude for Unreal Engine and PDFgear next steps.
pause
