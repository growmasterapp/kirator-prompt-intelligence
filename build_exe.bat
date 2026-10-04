@echo off
setlocal enabledelayedexpansion

echo.
echo ======================================================================
echo   KIRATOR PROMPT INTELLIGENCE - EXE BUILDER
echo ======================================================================
echo.
echo   This script packages your app into a standalone .exe
echo   that anyone can run - no Python needed on their machine.
echo.
echo ======================================================================
echo.

REM STEP 1: Check Python
echo   [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   Found Python %%v
echo.

REM STEP 2: Install PyInstaller
echo   [2/5] Installing PyInstaller...
pip install pyinstaller >nul 2>&1
echo   Done.
echo.

REM STEP 3: Check launcher
echo   [3/5] Preparing launcher...
if not exist "launcher.py" (
    echo   ERROR: launcher.py not found in project root.
    pause
    exit /b 1
)
echo   launcher.py found in project root.
echo.

REM STEP 4: Check src directory
if not exist "src\gui\app.py" (
    echo   ERROR: Cannot find src\gui\app.py
    echo   Please run this script from your project root:
    echo     C:\KIRATOR_PROMPT_INTELLIGENCE\build_exe.bat
    pause
    exit /b 1
)

echo   [4/5] Building executable...
echo   This will take a few minutes. Please wait...
echo.

pyinstaller --name "KiratorPromptIntelligence" --onedir --noconfirm --clean --console --add-data "src;src" --add-data "config;config" --add-data "requirements.txt;." --hidden-import=flask --hidden-import=jinja2 --hidden-import=markupsafe --hidden-import=httpx --hidden-import=httpx._transports --hidden-import=httpx._transports.default --hidden-import=ollama --hidden-import=yaml --hidden-import=numpy --hidden-import=chromadb --hidden-import=chromadb.config --hidden-import=chromadb.api --hidden-import=pydantic --hidden-import=tiktoken --hidden-import=src --hidden-import=src.gui --hidden-import=src.gui.app --hidden-import=src.core --hidden-import=src.core.models --hidden-import=src.core.json_utils --hidden-import=src.core.config --hidden-import=src.core.history_store --hidden-import=src.core.target_profiles --hidden-import=src.core.logging_setup --hidden-import=src.pipeline --hidden-import=src.pipeline.service --hidden-import=src.agents --hidden-import=src.agents.prompt_architect --hidden-import=src.models --hidden-import=src.models.ollama_client --hidden-import=src.models.embedding_client --hidden-import=src.stages --hidden-import=src.stages.stage1_router --hidden-import=src.stages.stage1_router.router --hidden-import=src.stages.stage2_intent_analyzer --hidden-import=src.stages.stage2_intent_analyzer.analyzer --hidden-import=src.stages.stage3_difficulty_analyzer --hidden-import=src.stages.stage3_difficulty_analyzer.analyzer --hidden-import=src.stages.stage4_strategy_planner --hidden-import=src.stages.stage4_strategy_planner.planner --hidden-import=src.stages.stage5_technique_selector --hidden-import=src.stages.stage5_technique_selector.selector --hidden-import=src.stages.stage6_prompt_composer --hidden-import=src.stages.stage6_prompt_composer.composer --hidden-import=src.stages.stage7_prompt_critic --hidden-import=src.stages.stage7_prompt_critic.critic --hidden-import=src.stages.stage8_optimizer --hidden-import=src.stages.stage8_optimizer.optimizer --hidden-import=src.stages.stage9_renderer --hidden-import=src.stages.stage9_renderer.renderer --collect-all chromadb --collect-all httpx --collect-all tiktoken launcher.py

echo.

REM STEP 5: Create distribution zip
echo   [5/5] Creating distribution zip...
if exist README.txt copy README.txt dist\KiratorPromptIntelligence\
powershell -Command "Compress-Archive -Path 'dist\KiratorPromptIntelligence' -DestinationPath 'dist\KiratorPromptIntelligence_v1.0.zip' -Force"
echo   Done.

echo.
echo ======================================================================
echo   BUILD COMPLETE
echo ======================================================================
echo.
echo   Your packaged application is ready:
echo.
echo   Executable folder: dist\KiratorPromptIntelligence\
echo   Distribution zip:  dist\KiratorPromptIntelligence_v1.0.zip
echo.
echo   TO TEST LOCALLY:
echo     Double-click: dist\KiratorPromptIntelligence\KiratorPromptIntelligence.exe
echo.
echo   TO SHARE WITH FRIENDS:
echo     Send them the zip file: dist\KiratorPromptIntelligence_v1.0.zip
echo     They unzip it, double-click the .exe, done.
echo.
echo   REQUIREMENT FOR USERS:
echo     They must have Ollama installed with these models:
echo       ollama pull deepseek-r1:8b
echo       ollama pull llama3.1:8b
echo.
echo ======================================================================

pause
