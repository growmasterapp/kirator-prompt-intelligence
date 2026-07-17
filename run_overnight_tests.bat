@echo off
chcp 65001 >nul 2>&1
title Kirator Overnight Ship-Readiness Battery
cd /d "%~dp0"

echo.
echo ======================================================================
echo   KIRATOR OVERNIGHT SHIP-READINESS BATTERY
echo   Unit + API + GUI + Pipeline (Ollama)
echo ======================================================================
echo.
echo   Tip: leave this running overnight. Reports land in test_results\
echo.

REM Ensure dev deps
python -c "import pytest" >nul 2>&1
if errorlevel 1 (
  echo Installing requirements-dev.txt ...
  python -m pip install -r requirements-dev.txt
)

REM Ensure Playwright Chromium once
python -c "from playwright.sync_api import sync_playwright" >nul 2>&1
if errorlevel 1 (
  echo Installing Playwright...
  python -m pip install playwright
)
python -m playwright install chromium >nul 2>&1

REM Default overnight: full pipeline once. Pass args through, e.g.:
REM   run_overnight_tests.bat --loops 3
REM   run_overnight_tests.bat --quick
python scripts\run_overnight_battery.py %*
set EXITCODE=%ERRORLEVEL%

echo.
echo ======================================================================
if %EXITCODE%==0 (
  echo   ALL CHECKS PASSED — review test_results\overnight_summary_*.md
) else (
  echo   SOME CHECKS FAILED — open the latest overnight_summary_*.md
)
echo ======================================================================
echo.
pause
exit /b %EXITCODE%
