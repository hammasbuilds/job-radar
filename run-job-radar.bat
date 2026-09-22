@echo off
REM One click: refresh everything, then open the dashboard.
REM
REM This runs BOTH fetches. An earlier version ran only the job crawl, so the
REM YC tab opened saying "Nothing yet. Run scripts/fetch_yc.py" - which is a
REM shortcut that does not shortcut anything. If a screen needs a command
REM typed before it works, the launcher is unfinished.
REM
REM The YC pass is skipped when its stored directory is under a day old. YC
REM batches move on a scale of weeks, so re-resolving 326 company boards every
REM launch would cost two minutes to learn nothing.
title job-radar
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
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
"%PY%" scripts\fetch.py
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
echo [3/3] Opening the dashboard at http://127.0.0.1:8000
echo.
echo   Close this window to stop it.
echo.
"%PY%" -m jobradar.api --port 8000
