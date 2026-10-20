@echo off
REM One click: refresh everything, then open the dashboard.
REM
REM This runs BOTH fetches. An earlier version ran only the job crawl, so the
REM YC tab opened saying "Nothing yet. Run scripts/fetch_yc.py" - which is a
REM shortcut that does not shortcut anything. If a screen needs a command
REM typed before it works, the launcher is unfinished.
REM
REM Both fetches are skipped when their stored data is still fresh - two hours
REM for the job crawl, a day for the YC directory. Twelve sources take about
REM five minutes, and a shortcut that sits on a console for five minutes before
REM showing anything is a shortcut nobody clicks twice. Postings do not turn
REM over in an hour and YC batches move on a scale of weeks.
title job-radar
cd /d "%~dp0"

REM Find a Python that can actually run this: this repo's own .venv first (the
REM one install.bat creates), then the standard per-user installs, then
REM whatever "python" is on PATH. Each candidate must import fastapi and
REM uvicorn; no other project's virtualenv is named here.
set "PY="
for %%P in (
    ".venv\Scripts\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
    "%APPDATA%\uv\python\cpython-3.11-windows-x86_64-none\python.exe"
) do if not defined PY if exist %%P (
    %%P -c "import fastapi, uvicorn" >nul 2>&1 && set "PY=%%~P"
)
if not defined PY (
    for /f "delims=" %%I in ('where python 2^>nul') do if not defined PY (
        "%%I" -c "import fastapi, uvicorn" >nul 2>&1 && set "PY=%%I"
    )
)
if not defined PY (
    echo.
    echo   No Python with fastapi and uvicorn was found.
    echo   Fix it by running install.bat, or by hand:
    echo       python -m venv "%~dp0.venv"
    echo       "%~dp0.venv\Scripts\python.exe" -m pip install -e "%~dp0."
    echo.
    pause
    exit /b 1
)

REM The package lives in src\ and is not installed, so `python -m jobradar.api`
REM cannot find it without this. Leaving it out is how the shortcut opened a
REM console that printed ModuleNotFoundError and closed.
set "PYTHONPATH=%~dp0src"

echo ============================================================
echo  job-radar
echo ============================================================
echo.
echo [1/3] Crawling job boards...
echo.
"%PY%" scripts\fetch.py --if-older-than 2
if errorlevel 1 (
    echo.
    echo   Crawl failed. The dashboard will still open with the last stored run.
)

echo.
echo [2/3] Refreshing the YC directory...
echo.
"%PY%" scripts\fetch_yc.py --if-older-than 24
if errorlevel 1 (
    echo.
    echo   YC refresh failed. The YC tab will show the last stored directory.
)

echo.
echo Refreshing the last three years of YC batches (weekly; LinkedIn from YC pages
echo is read by a separate full run: scripts\fetch_yc_recent.py)...
echo.
"%PY%" scripts\fetch_yc_recent.py --if-older-than 168 --no-pages
if errorlevel 1 (
    echo.
    echo   YC batch refresh failed. The recent-YC list will show the last stored copy.
)

echo.
echo Refreshing accelerator and investor portfolios (daily)...
echo.
"%PY%" scripts\fetch_portfolios.py --if-older-than 24
if errorlevel 1 (
    echo.
    echo   Portfolio refresh failed. The last stored portfolios stay on screen.
)

echo.
echo [3/3] Opening the dashboard at http://127.0.0.1:8000
echo.
echo   Close this window to stop it.
echo.
"%PY%" -m jobradar.api --port 8000
