@echo off
cd /d "%~dp0"
taskkill /f /im powershell.exe >nul 2>&1
set "DEST=C:\Users\YourUser\PortableGit"
set "SFX=%TEMP%\PortableGit255.7z.exe"
del FAST_GIT_LOG.txt 2>nul
if exist "%DEST%\cmd\git.exe" goto havegit
echo Downloading PortableGit via curl...
curl -L -s -o "%SFX%" https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.1/PortableGit-2.55.0-64-bit.7z.exe
echo Extracting to %DEST% ...
if not exist "%DEST%" mkdir "%DEST%"
start /wait "" "%SFX%" -o"%DEST%" -y
:havegit
powershell -NoProfile -Command "$p=[Environment]::GetEnvironmentVariable('Path','User'); if($null -eq $p){$p=''}; if($p -notlike '*PortableGit\cmd*'){[Environment]::SetEnvironmentVariable('Path',($p.TrimEnd(';')+';C:\Users\YourUser\PortableGit\cmd'),'User')}"
if exist "%DEST%\cmd\git.exe" (
  "%DEST%\cmd\git.exe" --version > FAST_GIT_LOG.txt 2>&1
  echo RESULT=SUCCESS >> FAST_GIT_LOG.txt
) else (
  echo git.exe NOT found at %DEST%\cmd > FAST_GIT_LOG.txt
  echo RESULT=FAIL >> FAST_GIT_LOG.txt
)
type FAST_GIT_LOG.txt
pause
