@echo off
chcp 65001 >nul 2>&1
title Kirator Prompt Intelligence
cd /d "%~dp0"

echo.
echo ======================================================================
echo   KIRATOR PROMPT INTELLIGENCE
echo   9-Stage AI Prompt Engineering Pipeline
echo ======================================================================
echo.

python launcher.py
if errorlevel 1 (
  echo.
  echo   Failed to start. Make sure Python is installed and Ollama is running.
  echo.
)

echo.
echo   Server stopped.
pause
