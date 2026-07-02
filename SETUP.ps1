<#
.SYNOPSIS
    Your Company Virtual Office v6.1.4 - Setup Script
    Houston, TX | Q2 2026 Build

.DESCRIPTION
    Single-run setup script. Checks for and installs all dependencies,
    configures API key templates, clears stale keyvault cache, creates
    folder structure, verifies connectivity, and runs a full health check.

    Run from the virtualoffice\ folder:
        powershell -ExecutionPolicy Bypass -File SETUP.ps1

.NOTES
    Author: Joseph Hasse, Director of I.T. Department
    Company: Your Company, LLC
    Version: 6.1.4
    Compat: Windows PowerShell 5.1+
#>

param(
    [switch]$SkipPython,
    [switch]$SkipPip,
    [switch]$SkipApiKeys,
    [switch]$SkipConnectivity,
    [switch]$Quiet
)

$ErrorActionPreference = "Continue"
$Version = "6.1.4"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $ScriptDir) { $ScriptDir = Get-Location }
Set-Location $ScriptDir

$LogFile = Join-Path $ScriptDir "setup_log.txt"
$Passed = 0
$Failed = 0
$Warned = 0

# ---- Helpers --------------------------------------------------------

function JP {
    # Join-Path wrapper that accepts 2+ segments (PS 5.1 safe)
    param([string[]]$Parts)
    $result = $Parts[0]
    for ($i = 1; $i -lt $Parts.Count; $i++) {
        $result = Join-Path $result $Parts[$i]
    }
    return $result
}

function Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -Path $LogFile -Value $line
    if (-not $Quiet) { Write-Host $line }
}

function Pass($msg) {
    $script:Passed++
    Log "[PASS] $msg"
}

function Fail($msg) {
    $script:Failed++
    $c = $Host.UI.RawUI.ForegroundColor
    $Host.UI.RawUI.ForegroundColor = "Red"
    Log "[FAIL] $msg"
    $Host.UI.RawUI.ForegroundColor = $c
}

function Warn($msg) {
    $script:Warned++
    $c = $Host.UI.RawUI.ForegroundColor
    $Host.UI.RawUI.ForegroundColor = "Yellow"
    Log "[WARN] $msg"
    $Host.UI.RawUI.ForegroundColor = $c
}

function Header($msg) {
    Log ""
    Log ("=" * 60)
    Log "  $msg"
    Log ("=" * 60)
}

# ---- Start ----------------------------------------------------------

"Your Company Virtual Office - Setup Log" | Set-Content $LogFile
"Version: $Version" | Add-Content $LogFile
"Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Add-Content $LogFile
"Machine: $env:COMPUTERNAME" | Add-Content $LogFile
"User: $env:USERNAME" | Add-Content $LogFile
"" | Add-Content $LogFile

Write-Host ""
Write-Host "  +---------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "  |   YOUR COMPANY - VIRTUAL OFFICE SETUP                  |" -ForegroundColor Cyan
Write-Host "  |   v$Version - Houston, TX - Q2 2026                       |" -ForegroundColor Cyan
Write-Host "  +---------------------------------------------------------+" -ForegroundColor Cyan
Write-Host ""

# =====================================================================
# STEP 1: PYTHON
# =====================================================================

Header "STEP 1: Python Environment"

if (-not $SkipPython) {
    $pyCmd = $null
    $pyVersion = $null
    $pyTarget = "3.13"
    $pyInstallerUrl = "https://www.python.org/ftp/python/3.13.9/python-3.13.9-amd64.exe"
    $pyInstallerFile = Join-Path $env:TEMP "python-3.13.9-amd64.exe"

    # Prefer 3.13 (latest stable). 3.14 is pre-release and breaks pythonnet/pywebview.
    foreach ($cmd in @("py -3.13", "py -3.12", "py -3.11", "python3", "python")) {
        try {
            $result = & cmd /c "$cmd --version 2>&1"
            if ($result -match "Python (\d+)\.(\d+)\.(\d+)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -eq 3 -and $minor -ge 11 -and $minor -le 13) {
                    $pyCmd = $cmd
                    $pyVersion = $result.Trim()
                    break
                }
            }
        } catch { }
    }

    # If only 3.14+ found or no Python at all, auto-install 3.13.9
    if (-not $pyCmd) {
        # Check if 3.14 is the only version
        $has314 = $false
        try {
            $result = & cmd /c "py -3 --version 2>&1"
            if ($result -match "Python 3\.(\d+)") {
                if ([int]$Matches[1] -ge 14) { $has314 = $true }
            }
        } catch { }

        if ($has314) {
            Log "  Python 3.14+ detected but pywebview requires 3.13 or lower."
        } else {
            Log "  No compatible Python found."
        }

        Log "  Downloading Python 3.13.9 (this takes about 30 seconds)..."
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $pyInstallerUrl -OutFile $pyInstallerFile -UseBasicParsing
            Log "  Download complete. Installing Python 3.13.9..."
            # /passive = show progress bar but no interaction
            # PrependPath=1 = add to PATH
            # Include_launcher=1 = install py.exe launcher
            # InstallAllUsers=0 = per-user install (no admin needed)
            $proc = Start-Process -FilePath $pyInstallerFile -ArgumentList "/passive InstallAllUsers=0 PrependPath=1 Include_launcher=1" -Wait -PassThru
            if ($proc.ExitCode -eq 0) {
                Log "  Python 3.13.9 installed successfully."
                # Refresh PATH in current session
                $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User")
                # Verify
                $verifyResult = & cmd /c "py -3.13 --version 2>&1"
                if ($verifyResult -match "Python 3\.13") {
                    $pyCmd = "py -3.13"
                    $pyVersion = $verifyResult.Trim()
                } else {
                    # py launcher may need a new shell to see it; try direct path
                    $userPy = JP @($env:LOCALAPPDATA, "Programs", "Python", "Python313", "python.exe")
                    if (Test-Path $userPy) {
                        $pyCmd = "`"$userPy`""
                        $pyVersion = "Python 3.13.9 (direct path)"
                    }
                }
            } else {
                Fail "Python installer exited with code $($proc.ExitCode)"
            }
        } catch {
            Fail "Python download failed: $($_.Exception.Message)"
            Log "  Manual install: https://www.python.org/ftp/python/3.13.9/python-3.13.9-amd64.exe"
        } finally {
            # Clean up installer
            if (Test-Path $pyInstallerFile) { Remove-Item $pyInstallerFile -Force -ErrorAction SilentlyContinue }
        }
    }

    if ($pyCmd) {
        Pass "Python found: $pyVersion (command: $pyCmd)"
    } else {
        Fail "Python 3.13 could not be installed automatically"
        Log "  Download manually: https://www.python.org/ftp/python/3.13.9/python-3.13.9-amd64.exe"
        Log "  Run the installer, check 'Add Python to PATH'"
        Log "  Close and reopen PowerShell, then re-run this script"
        Write-Host ""
        Write-Host "  Python install failed. Try the manual download link above." -ForegroundColor Red
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }

    # Upgrade pip
    Log "Upgrading pip..."
    & cmd /c "$pyCmd -m pip install --upgrade pip --quiet 2>&1" | Out-Null
    Pass "pip upgraded"
} else {
    Log "Skipping Python check (--SkipPython)"
    $pyCmd = "py -3.13"
}

# =====================================================================
# STEP 2: PIP DEPENDENCIES
# =====================================================================

Header "STEP 2: Python Package Dependencies"

if (-not $SkipPip) {

    $packages = @(
        # Core UI
        @{Name="pywebview";     Pip="pywebview>=5.0.0";   Import="webview";          Required=$true}

        # AI SDKs
        @{Name="anthropic";     Pip="anthropic";          Import="anthropic";        Required=$true}
        @{Name="openai";        Pip="openai";             Import="openai";           Required=$true}
        @{Name="google-genai";  Pip="google-genai";       Import="google.genai";     Required=$true;  Fallback="google-generativeai"; FallbackImport="google.generativeai"}

        # TLS (critical for Claude on Windows)
        @{Name="truststore";    Pip="truststore";         Import="truststore";       Required=$true}
        @{Name="httpx";         Pip="httpx";              Import="httpx";            Required=$true}
        @{Name="h2";            Pip="h2";                 Import="h2";               Required=$false}
        @{Name="requests";      Pip="requests";           Import="requests";         Required=$false}

        # PDF pipeline
        @{Name="pdfplumber";    Pip="pdfplumber";         Import="pdfplumber";       Required=$true}
        @{Name="PyMuPDF";       Pip="PyMuPDF";            Import="fitz";             Required=$true}
        @{Name="pymupdf4llm";   Pip="pymupdf4llm";       Import="pymupdf4llm";      Required=$true}
        @{Name="reportlab";     Pip="reportlab";          Import="reportlab";        Required=$true}

        # Engineering and data
        @{Name="pandas";        Pip="pandas";             Import="pandas";           Required=$true}
        @{Name="numpy";         Pip="numpy";              Import="numpy";            Required=$true}
        @{Name="fredapi";       Pip="fredapi";            Import="fredapi";          Required=$false}
        @{Name="Pillow";        Pip="Pillow";             Import="PIL";              Required=$false}
        @{Name="feedparser";    Pip="feedparser";         Import="feedparser";       Required=$false}
        @{Name="psutil";        Pip="psutil";             Import="psutil";           Required=$true}
        @{Name="openpyxl";      Pip="openpyxl";           Import="openpyxl";         Required=$true}

        # CAD, CNC, 3D
        @{Name="ezdxf";         Pip="ezdxf";              Import="ezdxf";            Required=$true}
        @{Name="numpy-stl";     Pip="numpy-stl";          Import="stl";              Required=$true}
        @{Name="trimesh";       Pip="trimesh";            Import="trimesh";          Required=$true}

        # Communications
        @{Name="twilio";        Pip="twilio";             Import="twilio";           Required=$false}
        @{Name="flask";         Pip="flask";              Import="flask";            Required=$false}

        # Platform
        @{Name="pywin32";       Pip="pywin32";            Import="win32com.client";  Required=$false}

        # Optional enhanced features
        @{Name="chromadb";      Pip="chromadb";           Import="chromadb";         Required=$false}
        @{Name="opencv";        Pip="opencv-python";      Import="cv2";              Required=$false}
        @{Name="qrcode";        Pip="qrcode";             Import="qrcode";           Required=$false}
    )

    $installed = 0
    $alreadyOk = 0
    $failedPkgs = @()

    foreach ($pkg in $packages) {
        $pName = $pkg.Name
        $importName = $pkg.Import

        # Check if already installed
        $checkResult = & cmd /c "$pyCmd -c `"import $importName`" 2>&1"
        if ($LASTEXITCODE -eq 0) {
            $alreadyOk++
            if (-not $Quiet) { Log "  ${pName} : already installed" }
            continue
        }

        # Not installed. Install it.
        Log "  Installing ${pName}..."
        $installResult = & cmd /c "$pyCmd -m pip install `"$($pkg.Pip)`" --quiet 2>&1"

        if ($LASTEXITCODE -ne 0) {
            # Try fallback if defined
            if ($pkg.Fallback) {
                Log "  ${pName} failed, trying fallback: $($pkg.Fallback)..."
                & cmd /c "$pyCmd -m pip install $($pkg.Fallback) --quiet 2>&1" | Out-Null
                $checkFallback = & cmd /c "$pyCmd -c `"import $($pkg.FallbackImport)`" 2>&1"
                if ($LASTEXITCODE -eq 0) {
                    $installed++
                    Warn "${pName}: using fallback $($pkg.Fallback)"
                    continue
                }
            }

            if ($pkg.Required) {
                Fail "${pName}: install failed (REQUIRED)"
                $failedPkgs += $pName
            } else {
                Warn "${pName}: install failed (optional, app works without it)"
            }
        } else {
            $installed++
            Log "  ${pName} : installed"
        }
    }

    Pass "Packages: $alreadyOk already installed, $installed newly installed"
    if ($failedPkgs.Count -gt 0) {
        Fail "Required packages failed: $($failedPkgs -join ', ')"
    }
} else {
    Log "Skipping pip install (--SkipPip)"
}

# =====================================================================
# STEP 3: API KEYS
# =====================================================================

Header "STEP 3: API Key Configuration"

if (-not $SkipApiKeys) {
    $keyDir = Join-Path $ScriptDir "API Keys"

    if (-not (Test-Path $keyDir)) {
        New-Item -ItemType Directory -Path $keyDir -Force | Out-Null
        Log "Created API Keys folder"
    }

    $keyFiles = @(
        @{File="Claude API.txt";  Prefix="sk-ant-"; Desc="Anthropic Claude"; Url="console.anthropic.com/settings/keys"}
        @{File="Gemini API.txt";  Prefix="AIza";    Desc="Google Gemini";    Url="aistudio.google.com/apikey"}
        @{File="OpenAI API.txt";  Prefix="sk-";     Desc="OpenAI GPT-4o";   Url="platform.openai.com/api-keys"}
    )

    foreach ($kf in $keyFiles) {
        $path = Join-Path $keyDir $kf.File
        if (-not (Test-Path $path)) {
            "$($kf.Prefix)REPLACE-WITH-YOUR-KEY" | Set-Content $path -NoNewline
            Warn "$($kf.File): template created. Paste your key from $($kf.Url)"
            continue
        }

        $content = (Get-Content $path -Raw).Trim()

        # Check for placeholder/instruction text
        if ($content -match "REPLACE|PASTE|YOUR.KEY|BELOW") {
            Warn "$($kf.File): still contains placeholder text. Get your key from $($kf.Url)"
            continue
        }

        # Check prefix
        if ($content.StartsWith($kf.Prefix)) {
            $preview = $content.Substring(0, [Math]::Min(12, $content.Length))
            Pass "$($kf.File): valid ($preview... $($content.Length) chars)"
        } else {
            Warn "$($kf.File): unexpected prefix (expected $($kf.Prefix)). Verify key is correct."
        }
    }

    # BlueBubbles key (optional)
    $bbPath = Join-Path $keyDir "BlueBubbles.txt"
    if (Test-Path $bbPath) {
        Log "  BlueBubbles.txt: present (iMessage gateway)"
    }
} else {
    Log "Skipping API key check (--SkipApiKeys)"
}

# =====================================================================
# STEP 4: KEYVAULT CACHE
# =====================================================================

Header "STEP 4: DPAPI Keyvault Cache"

$encPath = JP @($ScriptDir, "data", "keys.enc")
if (Test-Path $encPath) {
    $encSize = (Get-Item $encPath).Length
    if ($encSize -gt 0) {
        Log "  Clearing stale keyvault cache ($encSize bytes)..."
        Remove-Item $encPath -Force
        Pass "Keyvault cache cleared. App will re-encrypt from API Keys folder on next launch."
    }
} else {
    Pass "No stale keyvault cache found"
}

# =====================================================================
# STEP 5: FOLDER STRUCTURE
# =====================================================================

Header "STEP 5: Folder Structure"

$folders = @(
    (Join-Path $ScriptDir "data"),
    (JP @($env:USERPROFILE, "Documents", "Your Company Bids"))
)

foreach ($f in $folders) {
    if (-not (Test-Path $f)) {
        New-Item -ItemType Directory -Path $f -Force | Out-Null
        Log "  Created: $f"
    } else {
        Log "  Exists: $f"
    }
}

Pass "Folder structure verified"

# =====================================================================
# STEP 6: TESSERACT OCR (optional)
# =====================================================================

Header "STEP 6: Tesseract OCR (optional, for scanned PDF extraction)"

$tesseractPath = $null
$tesseractPaths = @(
    "C:\Program Files\Tesseract-OCR\tesseract.exe",
    "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    (JP @($env:LOCALAPPDATA, "Programs", "Tesseract-OCR", "tesseract.exe"))
)

foreach ($tp in $tesseractPaths) {
    if (Test-Path $tp) {
        $tesseractPath = $tp
        break
    }
}

if (-not $tesseractPath) {
    $tesseractInPath = Get-Command "tesseract" -ErrorAction SilentlyContinue
    if ($tesseractInPath) { $tesseractPath = $tesseractInPath.Source }
}

if ($tesseractPath) {
    $tVersion = & $tesseractPath --version 2>&1 | Select-Object -First 1
    Pass "Tesseract OCR found: $tVersion"
    $tesseractDir = Split-Path $tesseractPath
    if ($env:PATH -notlike "*$tesseractDir*") {
        [Environment]::SetEnvironmentVariable("PATH", "$env:PATH;$tesseractDir", "User")
        Log "  Added Tesseract to user PATH"
    }
} else {
    Warn "Tesseract OCR not installed. Scanned PDFs will use PyMuPDF built-in OCR (lower accuracy)."
    Log "  Install from: https://github.com/UB-Mannheim/tesseract/wiki"
}

# =====================================================================
# STEP 7: CONNECTIVITY
# =====================================================================

Header "STEP 7: API Connectivity"

if (-not $SkipConnectivity) {
    $endpoints = @(
        @{Name="Anthropic (Claude)"; Host="api.anthropic.com"; Port=443}
        @{Name="OpenAI (GPT-4o)";   Host="api.openai.com";    Port=443}
        @{Name="Google (Gemini)";    Host="generativelanguage.googleapis.com"; Port=443}
    )

    foreach ($ep in $endpoints) {
        try {
            $tcp = Test-NetConnection -ComputerName $ep.Host -Port $ep.Port -WarningAction SilentlyContinue -InformationLevel Quiet
            if ($tcp) {
                Pass "$($ep.Name): reachable"
            } else {
                Fail "$($ep.Name): port $($ep.Port) blocked. Check firewall/VPN."
            }
        } catch {
            Warn "$($ep.Name): connectivity test failed ($($_.Exception.Message))"
        }
    }

    # SSL certificate check
    Log ""
    Log "Checking SSL certificate chain (detecting proxy interception)..."
    try {
        $sslResult = & cmd /c "curl.exe -svI https://api.anthropic.com/v1/messages 2>&1" | Select-String "issuer"
        if ($sslResult) {
            $issuerLine = $sslResult.ToString().Trim()
            if ($issuerLine -match "Amazon|DigiCert|Let's Encrypt|Google Trust") {
                Pass "SSL: direct connection (issuer: $issuerLine)"
            } elseif ($issuerLine -match "Zscaler|BitDefender|Netskope|Forcepoint|Fortinet|SonicWall") {
                Warn "SSL: corporate proxy detected ($issuerLine). truststore package handles this."
            } else {
                Log "  SSL issuer: $issuerLine"
            }
        }
    } catch {
        Log "  SSL check skipped (curl.exe not available)"
    }
} else {
    Log "Skipping connectivity check (--SkipConnectivity)"
}

# =====================================================================
# STEP 8: VERIFICATION
# =====================================================================

Header "STEP 8: Full Verification"

$coreModules = @(
    @{Name="pywebview";     Test="import webview; print(getattr(webview, '__version__', 'OK'))"}
    @{Name="anthropic";     Test="import anthropic; print(anthropic.__version__)"}
    @{Name="openai";        Test="import openai; print(openai.__version__)"}
    @{Name="google-genai";  Test="from google import genai; print('OK')"}
    @{Name="httpx";         Test="import httpx; print(httpx.__version__)"}
    @{Name="truststore";    Test="import truststore; print('OK')"}
    @{Name="pdfplumber";    Test="import pdfplumber; print(pdfplumber.__version__)"}
    @{Name="PyMuPDF";       Test="import fitz; print(fitz.version[0])"}
    @{Name="pymupdf4llm";   Test="import pymupdf4llm; print('OK')"}
    @{Name="reportlab";     Test="import reportlab; print('OK')"}
    @{Name="pandas";        Test="import pandas; print(pandas.__version__)"}
    @{Name="numpy";         Test="import numpy; print(numpy.__version__)"}
    @{Name="openpyxl";      Test="import openpyxl; print(openpyxl.__version__)"}
    @{Name="ezdxf";         Test="import ezdxf; print(ezdxf.__version__)"}
    @{Name="numpy-stl";     Test="import stl; print('OK')"}
    @{Name="trimesh";       Test="import trimesh; print(trimesh.__version__)"}
    @{Name="psutil";        Test="import psutil; print(psutil.__version__)"}
)

$coreOk = 0
$coreFail = 0
foreach ($mod in $coreModules) {
    $result = & cmd /c "$pyCmd -c `"$($mod.Test)`" 2>&1"
    if ($LASTEXITCODE -eq 0) {
        $coreOk++
        Log "  $($mod.Name): $($result.Trim())"
    } else {
        $coreFail++
        Fail "$($mod.Name): import failed"
    }
}
Log ""
if ($coreFail -eq 0) {
    Pass "All $coreOk core packages verified"
} else {
    Fail "$coreFail core packages failed verification"
}

# Bridge module test
Log ""
Log "Testing bridge module imports..."
$bridgeTest = "import sys,os;sys.path.insert(0,'.');os.environ['YOURCO_SANDBOX']='1';from bridge.aisc_validator import AISCValidator;av=AISCValidator();from bridge.vm_bid_discovery import vm_evaluate_bid,_training_loaded;from bridge.virtual_owner import review_bid;from bridge.bid_sanity_gates import run_gates;from bridge.bid_pipeline import add_bid;print(f'AISC:{len(av.shape_list)} VM_TRAINED:{_training_loaded}')"
$bridgeResult = & cmd /c "$pyCmd -c `"$bridgeTest`" 2>&1"
if ($LASTEXITCODE -eq 0 -and $bridgeResult -match "AISC:2299") {
    Pass "Bridge modules: $($bridgeResult.Trim())"
} else {
    Fail "Bridge module import failed: $bridgeResult"
}

# Frontend check
Log ""
$htmlFile = JP @($ScriptDir, "frontend", "index.html")
$jsFile = JP @($ScriptDir, "frontend", "app.js")
if ((Test-Path $htmlFile) -and (Test-Path $jsFile)) {
    Pass "Frontend files present"
} else {
    Fail "Frontend files missing"
}

# Version consistency
Log ""
$versionTest = & cmd /c "$pyCmd -c `"import sys;sys.path.insert(0,'.');from vo_app import __version__;print(__version__)`" 2>&1"
if ($versionTest.Trim() -eq $Version) {
    Pass "Version consistent: $Version"
} else {
    Warn "Version mismatch: vo_app says $($versionTest.Trim()), expected $Version"
}

# =====================================================================
# SUMMARY
# =====================================================================

Header "SETUP COMPLETE"

$total = $Passed + $Failed + $Warned
Log ""
Log "  Python: $pyCmd ($pyVersion)"
Log "  Passed:   $Passed"
Log "  Warnings: $Warned"
Log "  Failed:   $Failed"
Log ""

if ($Failed -eq 0) {
    Write-Host ""
    Write-Host "  +---------------------------------------------------------+" -ForegroundColor Green
    Write-Host "  |   SETUP COMPLETE - ALL CHECKS PASSED                    |" -ForegroundColor Green
    Write-Host "  |                                                         |" -ForegroundColor Green
    Write-Host "  |   Next steps:                                           |" -ForegroundColor Green
    Write-Host "  |   1. Paste real API keys into the 'API Keys' folder     |" -ForegroundColor Green
    Write-Host "  |   2. Run: $pyCmd main.py                          |" -ForegroundColor Green
    Write-Host "  |                                                         |" -ForegroundColor Green
    Write-Host "  |   Troubleshooting: .\DIAGNOSE_CLAUDE.bat                |" -ForegroundColor Green
    Write-Host "  +---------------------------------------------------------+" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  +---------------------------------------------------------+" -ForegroundColor Red
    Write-Host "  |   SETUP INCOMPLETE - $Failed FAILURE(S)                        |" -ForegroundColor Red
    Write-Host "  |                                                         |" -ForegroundColor Red
    Write-Host "  |   Review the failures above and fix before launching.   |" -ForegroundColor Red
    Write-Host "  |   Log saved to: setup_log.txt                           |" -ForegroundColor Red
    Write-Host "  |   Email to: joseph@yourcompany.example.com if stuck             |" -ForegroundColor Red
    Write-Host "  +---------------------------------------------------------+" -ForegroundColor Red
}

Log ""
Log "Full log saved to: $LogFile"
Write-Host ""
