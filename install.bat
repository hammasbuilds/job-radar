@echo off
REM Install job-radar for personal use: its own virtualenv, the package, a
REM shortcut, and a pin. Nothing is installed into any other Python.
setlocal
cd /d "%~dp0"

echo === job-radar install ===
echo.

echo [1/3] Creating .venv and installing the package...
if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>&1 && (py -3 -m venv .venv) || (python -m venv .venv)
)
if not exist ".venv\Scripts\python.exe" (
    echo   Could not create .venv. Install Python 3.11+ from python.org and try again.
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -e ".[dev]"
if errorlevel 1 (
    echo   pip failed. Check the network, then run install.bat again.
    exit /b 1
)
echo   .venv ready: fastapi, uvicorn, pytest and job-radar itself.
echo.

echo [2/3] Creating the shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-shortcut.ps1"
echo.

echo [3/3] Done.
echo.
echo   Desktop shortcut : job-radar
echo   Start menu       : job-radar
echo.
echo   Windows 11 blocks pinning to the taskbar from a script, so the last
echo   step is manual and takes two seconds: press Start, type job-radar,
echo   right-click it, choose "Pin to taskbar".
echo.
pause
