@echo off
REM Refresh the corpus, then open the dashboard. One click, personal use.
REM
REM The fetch runs first and is quiet unless something breaks: opening a
REM dashboard showing yesterday's list is how a tool stops being trusted.
REM With the HTTP cache warm this takes about half a minute.
title job-radar
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo Refreshing job-radar...
echo.
"%PY%" scripts\fetch.py
if errorlevel 1 (
    echo.
    echo Fetch failed. The dashboard will still open with the last stored run.
    echo.
)

echo.
echo Opening the dashboard. Close this window to stop it.
"%PY%" -m jobradar.api --port 8000
