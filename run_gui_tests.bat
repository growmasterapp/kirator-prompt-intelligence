@echo off
chcp 65001 >nul 2>&1
title Kirator GUI Tests
cd /d "%~dp0"

echo.
echo ======================================================================
echo   KIRATOR GUI AUTOMATION (Playwright)
echo ======================================================================
echo.

python -c "import pytest, playwright" >nul 2>&1
if errorlevel 1 (
  echo Installing test dependencies...
  python -m pip install -r requirements-dev.txt
  python -m playwright install chromium
)

echo Running GUI chrome tests (no full pipeline)...
python -m pytest tests\gui -m "gui and not e2e" -v --tb=short
set CODE=%ERRORLEVEL%

echo.
echo Optional: full E2E GUI pipeline (needs Ollama, can take several minutes)
echo   python -m pytest tests\gui -m e2e -v --timeout=900
echo.

if %CODE%==0 (
  echo GUI chrome tests PASSED
) else (
  echo GUI chrome tests FAILED
)
pause
exit /b %CODE%
