@echo off
REM Install job-radar for personal use: dependencies, a shortcut, and a pin.
setlocal
cd /d "%~dp0"

echo === job-radar install ===
echo.

echo [1/3] Installing dependencies...
python -m pip install --quiet --upgrade fastapi uvicorn
if errorlevel 1 (
    echo   pip failed. Install Python 3.11+ and try again.
    exit /b 1
)
echo   fastapi, uvicorn ready.
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
