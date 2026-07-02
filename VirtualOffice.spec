# VirtualOffice.spec
# PyInstaller spec for Your Company Virtual Office v3.2.7
#
# CRITICAL: Python packages use collect_submodules() - NOT --add-data.
# Using --add-data for .py packages causes:
#   "TypeError: function() argument 'code' must be code, not str"
#
# Build: py -3.13 -m PyInstaller VirtualOffice.spec --noconfirm --clean
# Or:    make_exe.bat (calls this automatically)

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

# ── Python packages (compiled via collect_submodules — not --add-data) ───
hidden = []
hidden += collect_submodules('vo_app')
hidden += collect_submodules('bridge')
hidden += collect_submodules('harnesses')   # v3.5.2 self-test operational harnesses
hidden += collect_submodules('webview')
hidden += collect_submodules('anthropic')
hidden += ['anthropic._legacy_response', 'anthropic.types', 'anthropic.resources']
hidden += collect_submodules('openai')
hidden += collect_submodules('google')
hidden += collect_submodules('google.genai')   # v3.5.6: was google.generativeai
hidden += collect_submodules('reportlab')
hidden += collect_submodules('openpyxl')   # v3.3.31: PC1 budget reader. Only
# imported lazily (bridge/project_controls.py _load_baseline, takeoff_pipeline
# budget_convert/shop_log), so it must be collected explicitly. et_xmlfile
# rides in transitively. Next signed build must be re-cut to pick this up.
hidden += ['psutil']
# BUG-008 FIX: psutil._psutil_linux and psutil._psutil_posix do not exist on
# Windows and cause "module not found" warnings on every make_exe.bat run.

# ── Non-Python assets (datas — these ARE --add-data equivalents) ─────────
datas = [
    (str(Path('frontend').resolve()), 'frontend'),
    (str(Path('data').resolve()),     'data'),
    # BUG-005 FIX: skills/ was missing. SkillRegistry resolves paths relative
    # to __file__ at runtime, so all 10 SKILL.md files were absent in the EXE.
    # Every skill match returned nothing in production. assets/ added for icons.
    (str(Path('skills').resolve()),   'skills'),
    (str(Path('assets').resolve()),   'assets'),
]

# collect_all bundles data files (proto/JSON schemas) alongside submodules
_genai = collect_all('google.genai')
datas += _genai[0]; hidden += _genai[2]
_gauth = collect_all('google.auth')
datas += _gauth[0]; hidden += _gauth[2]

a = Analysis(
    ['main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=['hooks'],   # v3.5.6: hooks/hook-tesseract.py bundles OCR
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI frameworks not used
        'tkinter', 'PyQt5', 'PyQt6', 'wx', 'PySide2', 'PySide6',
        # Heavy ML/vision packages (app uses Gemini vision instead)
        'torch', 'torchvision', 'torchaudio',
        'scipy', 'sklearn', 'scikit-image', 'skimage',
        'cv2', 'opencv-python',
        'easyocr', 'onnxruntime',
        'tensorflow', 'transformers',
        # Plotting (not used in desktop app)
        'matplotlib', 'seaborn', 'plotly', 'bokeh',
        # Dev/test tools
        'pytest', 'sphinx', 'IPython', 'jupyter', 'notebook',
        'test', 'unittest',
        # Unused heavy submodules
        'pandas.tests', 'numpy.tests', 'numpy.f2py',
        'PIL.ImageQt',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YourCoVirtualOffice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no black window — errors go to launch.log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YourCoVirtualOffice',
)
