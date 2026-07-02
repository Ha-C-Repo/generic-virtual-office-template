@echo off
:: Your Company Virtual Office - Working Tree Recovery
:: Restores bridge/ from git HEAD and clears all .pyc caches.
:: Run this whenever VirtualOffice crashes on launch or self-test fails.
::
:: Does NOT rely on git hooks (post-checkout does not fire on path-spec
:: checkouts like "git checkout HEAD -- bridge/"). Clears pyc explicitly.

setlocal
cd /d "%~dp0"

echo [RECOVER] Restoring bridge/ from git HEAD...
git checkout HEAD -- bridge/
if errorlevel 1 (
    echo [RECOVER] ERROR: git checkout failed. Are you in the right directory?
    pause
    exit /b 1
)

echo [RECOVER] Clearing __pycache__ directories...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)

echo [RECOVER] Recompiling bridge/ ...
py -m compileall bridge/ -q
if errorlevel 1 (
    echo [RECOVER] ERROR: bridge/ still has compile errors after recovery.
    echo [RECOVER] Run: py -m compileall bridge/ to see details.
    pause
    exit /b 1
)

echo [RECOVER] Done. Run "py main.py" or "self test" in chat to verify.
endlocal
