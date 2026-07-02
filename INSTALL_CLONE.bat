@echo off
cd /d "%~dp0"
echo ============================================================
echo  YOUR COMPANY VIRTUAL OFFICE - CLONE / PARITY INSTALL
echo ============================================================
echo.
echo [1/3] Installing pytest-mock (test dependency)...
where py >nul 2>&1
if %errorlevel%==0 (py -3 -m pip install pytest-mock) else (python -m pip install pytest-mock)
echo.
echo [2/3] Installing Git for Windows via winget...
where winget >nul 2>&1
if %errorlevel%==0 (
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
) else (
  echo winget NOT found - Git must be installed manually from https://git-scm.com/download/win
)
echo.
echo [3/3] Installing Tesseract OCR via winget (optional, for pymupdf4llm OCR)...
where winget >nul 2>&1
if %errorlevel%==0 (
  winget install --id UB-Mannheim.TesseractOCR -e --source winget --accept-package-agreements --accept-source-agreements
) else (
  echo winget NOT found - Tesseract skipped.
)
echo.
echo ============================================================
echo  DONE. Approve any Windows UAC prompts that appear.
echo ============================================================
pause
