@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo.
echo ======================================================================
echo   KIRATOR PROMPT INTELLIGENCE - EXE BUILDER
echo ======================================================================
echo.
echo   This script packages your app into a standalone .exe
echo   that anyone can run — no Python needed on their machine.
echo.
echo ======================================================================
echo.

:: -------------------------------------------------------
:: STEP 0: Verify we're in the right directory
:: -------------------------------------------------------
if not exist "src\gui\app.py" (
    echo   ERROR: Cannot find src\gui\app.py
    echo   Please run this script from your project root:
    echo     C:\KIRATOR_PROMPT_INTELLIGENCE\build_exe.bat
    echo.
    pause
    exit /b 1
)

:: -------------------------------------------------------
:: STEP 1: Check Python
:: -------------------------------------------------------
echo   [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python is not installed or not in PATH.
    echo   Download it from https://python.org
    echo   IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   Found Python %%v
echo.

:: -------------------------------------------------------
:: STEP 2: Install PyInstaller
:: -------------------------------------------------------
echo   [2/5] Installing PyInstaller...
pip install pyinstaller >nul 2>&1
if errorlevel 1 (
    echo   WARNING: PyInstaller install may have had issues.
    echo   Trying to continue anyway...
)
echo   Done.
echo.

:: -------------------------------------------------------
:: STEP 3: Copy launcher.py to project root if needed
:: -------------------------------------------------------
echo   [3/5] Preparing launcher...
if not exist "launcher.py" (
    if exist "scripts\launcher.py" (
        copy "scripts\launcher.py" "launcher.py" >nul 2>&1
        echo   Copied launcher.py from scripts\
    ) else (
        echo   WARNING: launcher.py not found!
        echo   The build may still work if you have it in the root.
    )
) else (
    echo   launcher.py found in project root.
)
echo.

:: -------------------------------------------------------
:: STEP 4: Build the PyInstaller arguments dynamically
::    Only include data directories that actually exist.
:: -------------------------------------------------------
echo   [4/5] Building executable...
echo   This will take a few minutes. Please wait...
echo.

:: Start building the PyInstaller command
set PYARGS=--name "KiratorPromptIntelligence"
set PYARGS=%PYARGS% --onedir
set PYARGS=%PYARGS% --noconfirm
set PYARGS=%PYARGS% --clean

:: Use console mode (shows terminal window) so users can see startup
:: and any errors. Change to --windowed for final release if desired.
set PYARGS=%PYARGS% --console

:: Add data directories that exist
:: Syntax for PyInstaller on Windows: source;destination

:: Add the entire src directory (Python modules)
if exist "src" (
    set PYARGS=%PYARGS% --add-data "src;src"
)

:: Add config directory (YAML files, etc.)
if exist "config" (
    set PYARGS=%PYARGS% --add-data "config;config"
)

:: Add data directory (ChromaDB, embeddings, etc.)
if exist "data" (
    set PYARGS=%PYARGS% --add-data "data;data"
)

:: Add technique store if it exists in a separate location
if exist "technique_store" (
    set PYARGS=%PYARGS% --add-data "technique_store;technique_store"
)

:: Add requirements.txt if exists (for reference)
if exist "requirements.txt" (
    set PYARGS=%PYARGS% --add-data "requirements.txt;."
)

:: Hidden imports — explicitly tell PyInstaller about modules
:: it might miss due to dynamic imports
set PYARGS=%PYARGS% --hidden-import=flask
set PYARGS=%PYARGS% --hidden-import=flask_cors
set PYARGS=%PYARGS% --hidden-import=jinja2
set PYARGS=%PYARGS% --hidden-import=markupsafe
set PYARGS=%PYARGS% --hidden-import=httpx
set PYARGS=%PYARGS% --hidden-import=httpx._transports
set PYARGS=%PYARGS% --hidden-import=httpx._transports.default
set PYARGS=%PYARGS% --hidden-import=ollama
set PYARGS=%PYARGS% --hidden-import=yaml
set PYARGS=%PYARGS% --hidden-import=numpy
set PYARGS=%PYARGS% --hidden-import=chromadb
set PYARGS=%PYARGS% --hidden-import=chromadb.config
set PYARGS=%PYARGS% --hidden-import=chromadb.api
set PYARGS=%PYARGS% --hidden-import=pydantic
set PYARGS=%PYARGS% --hidden-import=tiktoken

:: Explicitly list all stage modules
set PYARGS=%PYARGS% --hidden-import=src
set PYARGS=%PYARGS% --hidden-import=src.gui
set PYARGS=%PYARGS% --hidden-import=src.gui.app
set PYARGS=%PYARGS% --hidden-import=src.core
set PYARGS=%PYARGS% --hidden-import=src.core.models
set PYARGS=%PYARGS% --hidden-import=src.core.json_utils
set PYARGS=%PYARGS% --hidden-import=src.models
set PYARGS=%PYARGS% --hidden-import=src.models.ollama_client
set PYARGS=%PYARGS% --hidden-import=src.stages
set PYARGS=%PYARGS% --hidden-import=src.stages.stage1_router
set PYARGS=%PYARGS% --hidden-import=src.stages.stage1_router.router
set PYARGS=%PYARGS% --hidden-import=src.stages.stage2_intent_analyzer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage2_intent_analyzer.analyzer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage3_difficulty_analyzer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage3_difficulty_analyzer.analyzer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage4_strategy_planner
set PYARGS=%PYARGS% --hidden-import=src.stages.stage4_strategy_planner.planner
set PYARGS=%PYARGS% --hidden-import=src.stages.stage5_technique_selector
set PYARGS=%PYARGS% --hidden-import=src.stages.stage5_technique_selector.selector
set PYARGS=%PYARGS% --hidden-import=src.stages.stage6_prompt_composer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage6_prompt_composer.composer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage7_prompt_critic
set PYARGS=%PYARGS% --hidden-import=src.stages.stage7_prompt_critic.critic
set PYARGS=%PYARGS% --hidden-import=src.stages.stage8_optimizer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage8_optimizer.optimizer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage9_renderer
set PYARGS=%PYARGS% --hidden-import=src.stages.stage9_renderer.renderer

:: Collect all sub-modules from complex packages
set PYARGS=%PYARGS% --collect-all chromadb
set PYARGS=%PYARGS% --collect-all httpx
set PYARGS=%PYARGS% --collect-all tiktoken

:: Entry point
set PYARGS=%PYARGS% launcher.py

:: Run PyInstaller
echo   Running: pyinstaller %PYARGS%
echo.
pyinstaller %PYARGS%

if errorlevel 1 (
    echo.
    echo ======================================================================
    echo   BUILD FAILED!
    echo ======================================================================
    echo.
    echo   Check the error messages above. Common fixes:
    echo.
    echo   1. Missing module? Add it as --hidden-import above
    echo   2. Missing data file? Add it as --add-data above
    echo   3. Path error? Make sure you're in the project root
    echo.
    pause
    exit /b 1
)

echo.

:: -------------------------------------------------------
:: STEP 5: Create distribution zip
:: -------------------------------------------------------
echo   [5/5] Creating distribution zip...

set DIST_DIR=dist\KiratorPromptIntelligence
set ZIP_NAME=KiratorPromptIntelligence_v1.0.zip

if not exist "%DIST_DIR%\KiratorPromptIntelligence.exe" (
    echo   ERROR: Expected exe not found at %DIST_DIR%
    echo   The build may have used a different name.
    pause
    exit /b 1
)

:: Use PowerShell to create the zip (available on Windows 10+)
powershell -Command "if (Test-Path 'dist\%ZIP_NAME%') { Remove-Item 'dist\%ZIP_NAME%' -Force }; Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath 'dist\%ZIP_NAME%' -Force"

if exist "dist\%ZIP_NAME%" (
    echo   Done!
) else (
    echo   WARNING: Could not create zip file.
    echo   You can manually zip the folder: dist\KiratorPromptIntelligence\
)

:: -------------------------------------------------------
:: DONE
:: -------------------------------------------------------
echo.
echo ======================================================================
echo   BUILD COMPLETE!
echo ======================================================================
echo.
echo   Your packaged application is ready:
echo.
echo   Executable folder: dist\KiratorPromptIntelligence\
echo   Distribution zip:  dist\%ZIP_NAME%
echo.
echo   TO TEST LOCALLY:
echo     Double-click: dist\KiratorPromptIntelligence\KiratorPromptIntelligence.exe
echo.
echo   TO SHARE WITH FRIENDS:
echo     Send them the zip file: dist\%ZIP_NAME%
echo     They unzip it, double-click the .exe, done.
echo.
echo   REQUIREMENT FOR USERS:
echo     They must have Ollama installed with these models:
echo       ollama pull deepseek-r1:8b
echo       ollama pull llama3.1:8b
echo.
echo ======================================================================
echo.
pause