@echo off
REM ================================================================
REM  YOUR COMPANY VIRTUAL OFFICE - DEPENDENCY INSTALLER
REM  v3.2.7 - Updated May 2026
REM  Run this ONCE before first launch. Installs all Python packages.
REM  After this completes, run: RUN_VIRTUALOFFICE.bat
REM ================================================================

echo.
echo  +=========================================================+
echo  !       YOUR COMPANY - VIRTUAL OFFICE INSTALLER          !
echo  !       v3.2.7 - Houston, TX - Q2 2026 Build             !
echo  +=========================================================+
echo.

REM -- Check Python ------------------------------------------------
echo [1/10] Checking Python installation...
where py >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found!
    echo  Install Python 3.11+ from https://www.python.org/downloads/
    echo  IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
py -3 --version 2>nul || py --version

REM -- Upgrade pip -------------------------------------------------
echo.
echo [2/10] Upgrading pip...
py -3 -m pip install --upgrade pip --quiet 2>nul

REM -- Core UI -----------------------------------------------------
echo.
echo [3/10] Installing core UI (pywebview)...
py -3 -m pip install "pywebview>=5.0.0" --quiet
if %errorlevel% neq 0 (
    echo  WARNING: pywebview install issue. Trying alternate...
    py -m pip install pywebview --quiet
)

REM -- AI Provider SDKs --------------------------------------------
echo.
echo [4/10] Installing AI provider SDKs...
py -3 -m pip install anthropic --quiet
py -3 -m pip install openai --quiet
py -3 -m pip install google-genai --quiet
if %errorlevel% neq 0 (
    echo  WARNING: google-genai failed. Installing legacy package...
    py -3 -m pip install google-generativeai --quiet
)

REM -- TLS Fix (CRITICAL for Claude on Windows) --------------------
echo.
echo [5/10] Installing TLS and HTTP libraries...
py -3 -m pip install truststore --quiet
py -3 -m pip install httpx --quiet
py -3 -m pip install h2 --quiet
py -3 -m pip install requests --quiet

REM -- PDF Pipeline ------------------------------------------------
echo.
echo [6/10] Installing PDF pipeline...
py -3 -m pip install pdfplumber --quiet
py -3 -m pip install PyMuPDF --quiet
py -3 -m pip install pymupdf4llm --quiet
py -3 -m pip install reportlab --quiet

REM -- Engineering and Data ----------------------------------------
echo.
echo [7/10] Installing engineering and data libraries...
py -3 -m pip install pandas --quiet
py -3 -m pip install numpy --quiet
py -3 -m pip install fredapi --quiet
py -3 -m pip install Pillow --quiet
py -3 -m pip install feedparser --quiet
py -3 -m pip install psutil --quiet
py -3 -m pip install openpyxl --quiet
py -3 -m pip install flask --quiet
py -3 -m pip install twilio --quiet

REM -- CAD, CNC, and 3D -------------------------------------------
echo.
echo [8/10] Installing CAD, CNC, and 3D libraries...
py -3 -m pip install ezdxf --quiet
py -3 -m pip install numpy-stl --quiet
py -3 -m pip install trimesh --quiet

REM -- Communications and Platform ---------------------------------
echo.
echo [9/10] Installing communications and platform libraries...
py -3 -m pip install twilio --quiet
py -3 -m pip install pywin32 --quiet 2>nul
if %errorlevel% neq 0 (
    echo  NOTE: pywin32 skipped. Outlook inbox scanning requires this on Windows.
)

echo.
echo  Installing optional enhanced features (guarded - app works without them)...
py -3 -m pip install chromadb --quiet 2>nul
if %errorlevel% neq 0 echo  NOTE: chromadb skipped. Project memory uses JSONL fallback.
py -3 -m pip install opencv-python --quiet 2>nul
if %errorlevel% neq 0 echo  NOTE: opencv-python skipped. Ghost overlay unavailable.
py -3 -m pip install qrcode --quiet 2>nul
if %errorlevel% neq 0 echo  NOTE: qrcode skipped. QR labels return URL only.

REM -- Verification ------------------------------------------------
echo.
echo [10/10] Verifying installation...
py -3 -c "import webview; print('  pywebview:', webview.__version__)" 2>nul || echo  pywebview: FAILED
py -3 -c "import anthropic; print('  anthropic:', anthropic.__version__)" 2>nul || echo  anthropic: FAILED
py -3 -c "import openai; print('  openai:', openai.__version__)" 2>nul || echo  openai: FAILED
py -3 -c "from google import genai; print('  google-genai: OK')" 2>nul || (py -3 -c "import google.generativeai; print('  google-generativeai: OK [legacy]')" 2>nul || echo  google AI SDK: FAILED)
py -3 -c "import httpx; print('  httpx:', httpx.__version__)" 2>nul || echo  httpx: FAILED
py -3 -c "import truststore; print('  truststore: OK')" 2>nul || echo  truststore: FAILED
py -3 -c "import pdfplumber; print('  pdfplumber:', pdfplumber.__version__)" 2>nul || echo  pdfplumber: FAILED
py -3 -c "import fitz; print('  PyMuPDF:', fitz.version[0])" 2>nul || echo  PyMuPDF: FAILED
py -3 -c "import pandas; print('  pandas:', pandas.__version__)" 2>nul || echo  pandas: FAILED
py -3 -c "import numpy; print('  numpy:', numpy.__version__)" 2>nul || echo  numpy: FAILED
py -3 -c "import reportlab; print('  reportlab: OK')" 2>nul || echo  reportlab: FAILED
py -3 -c "import openpyxl; print('  openpyxl:', openpyxl.__version__)" 2>nul || echo  openpyxl: FAILED
py -3 -c "import ezdxf; print('  ezdxf:', ezdxf.__version__)" 2>nul || echo  ezdxf: FAILED
py -3 -c "import fredapi; print('  fredapi: OK')" 2>nul || echo  fredapi: FAILED
py -3 -c "import psutil; print('  psutil:', psutil.__version__)" 2>nul || echo  psutil: FAILED
py -3 -c "import stl; print('  numpy-stl: OK')" 2>nul || echo  numpy-stl: FAILED
py -3 -c "import trimesh; print('  trimesh:', trimesh.__version__)" 2>nul || echo  trimesh: FAILED

echo.
echo  Optional features:
py -3 -c "import chromadb; print('  chromadb: OK (project memory)')" 2>nul || echo  chromadb: not installed (JSONL fallback active)
py -3 -c "import cv2; print('  opencv:', cv2.__version__)" 2>nul || echo  opencv: not installed (ghost overlay unavailable)
py -3 -c "import qrcode; print('  qrcode: OK')" 2>nul || echo  qrcode: not installed (QR labels return URL only)

echo.
echo  +=========================================================+
echo  !  INSTALLATION COMPLETE - v3.2.7                         !
echo  !                                                         !
echo  !  Next steps:                                            !
echo  !  1. Verify API keys are in the "API Keys" folder        !
echo  !  2. Run: RUN_VIRTUALOFFICE.bat                          !
echo  +=========================================================+
echo.
pause
