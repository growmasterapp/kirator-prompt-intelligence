@echo off
chcp 65001 >nul 2>&1
title Kirator Prompt Intelligence

echo.
echo ======================================================================
echo   KIRATOR PROMPT INTELLIGENCE
echo   9-Stage AI Prompt Engineering Pipeline
echo ======================================================================
echo.
echo   Starting server...
echo   Your browser will open automatically.
echo   Press Ctrl+C to stop.
echo.
echo ======================================================================
echo.

:: Wait 2 seconds for the server to start, then open the browser
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

:: Start the Flask server
python -c "from src.gui.app import app; app.run(host='127.0.0.1', port=5000, threaded=True)"

:: If the server stops, keep the window open so user can see any errors
echo.
echo   Server stopped.
pause