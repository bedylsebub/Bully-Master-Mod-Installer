@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)
%PY% -m venv .venv
if errorlevel 1 goto :failed
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
call ".venv\Scripts\python.exe" -m pip install "pyinstaller>=6,<7"
if errorlevel 1 goto :failed
call ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name BullyModPatcher BullyModPatcher.py
if errorlevel 1 goto :failed
echo.
echo Build complete: dist\BullyModPatcher.exe
exit /b 0
:failed
echo Build failed. Check the messages above.
exit /b 1
