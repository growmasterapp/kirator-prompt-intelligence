@echo off
REM ============================================================
REM Kirator Prompt Intelligence — Run Test Battery
REM ============================================================
REM Drop this file in your project root (C:\KIRATOR_PROMPT_INTELLIGENCE\)
REM along with the scripts\test_battery.py file.
REM
REM Usage:
REM   run_tests.bat              Full 14-test battery
REM   run_tests.bat --quick      Quick 4-test smoke test
REM   run_tests.bat --id T03     Run a single test
REM   run_tests.bat --target claude   Only Claude targets
REM   run_tests.bat --parallel 2      Run 2 tests at once
REM ============================================================

echo ============================================================
echo   KIRATOR PROMPT INTELLIGENCE - TEST BATTERY
echo ============================================================
echo.

REM Check if Ollama is running
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Ollama is not running! Start it first:
    echo   ollama serve
    echo.
    pause
    exit /b 1
)

echo Ollama is running. Starting test battery...
echo.

REM Run the test battery (pass any CLI args through)
python scripts\test_battery.py %*

echo.
pause