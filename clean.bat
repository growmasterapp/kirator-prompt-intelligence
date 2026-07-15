@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo.
echo ======================================================================
echo   KIRATOR PROMPT INTELLIGENCE - CLEANUP SCRIPT
echo ======================================================================
echo.
echo   This removes dead weight before packaging.
echo   Nothing here is used by the running application.
echo.

set KILLED=0
set SAVED=0

:: -------------------------------------------------------
:: 1. ALL __pycache__ directories (regenerate automatically)
:: -------------------------------------------------------
echo   [1/7] Removing __pycache__ directories...
for /d /r %%d in (__pycache__) do (
    if exist "%%d" (
        rd /s /q "%%d" 2>nul
        set /a KILLED+=1
    )
)
echo   Done.

:: -------------------------------------------------------
:: 2. Old CLI script (app.py is the real entry point)
:: -------------------------------------------------------
echo   [2/7] Removing old CLI script...
if exist "kirator.py" (
    del /q "kirator.py"
    set /a KILLED+=1
    echo     Removed kirator.py
)

:: -------------------------------------------------------
:: 3. Duplicate files
:: -------------------------------------------------------
echo   [3/7] Removing duplicates...
if exist "test_battery.py" (
    del /q "test_battery.py"
    set /a KILLED+=1
    echo     Removed test_battery.py (duplicate of scripts\test_battery.py)
)
if exist "src\gui\index.html" (
    del /q "src\gui\index.html"
    set /a KILLED+=1
    echo     Removed src\gui\index.html (duplicate of templates\index.html)
)
if exist "startserver.txt" (
    del /q "startserver.txt"
    set /a KILLED+=1
    echo     Removed startserver.txt
)
if exist "log.txt" (
    del /q "log.txt"
    set /a KILLED+=1
    echo     Removed log.txt
)

:: -------------------------------------------------------
:: 4. Backup files
:: -------------------------------------------------------
echo   [4/7] Removing .bak files...
if exist "src\core\models.py.bak" (
    del /q "src\core\models.py.bak"
    set /a KILLED+=1
    echo     Removed src\core\models.py.bak
)
if exist "src\stages\stage1_router\router.py.bak" (
    del /q "src\stages\stage1_router\router.py.bak"
    set /a KILLED+=1
    echo     Removed src\stages\stage1_router\router.py.bak
)

:: -------------------------------------------------------
:: 5. Unused modules (not imported by app.py or any stage)
:: -------------------------------------------------------
echo   [5/7] Removing unused modules...
if exist "src\core\memory.py" (
    del /q "src\core\memory.py"
    set /a KILLED+=1
    echo     Removed src\core\memory.py (never imported)
)
if exist "src\core\adaptive_length.py" (
    del /q "src\core\adaptive_length.py"
    set /a KILLED+=1
    echo     Removed src\core\adaptive_length.py (never imported)
)
if exist "src\core\confidence.py" (
    del /q "src\core\confidence.py"
    set /a KILLED+=1
    echo     Removed src\core\confidence.py (never imported)
)
if exist "src\core\model_profiles.py" (
    del /q "src\core\model_profiles.py"
    set /a KILLED+=1
    echo     Removed src\core\model_profiles.py (never imported)
)
if exist "src\stages\reverse_engineer" (
    rd /s /q "src\stages\reverse_engineer"
    set /a KILLED+=1
    echo     Removed src\stages\reverse_engineer\ (not wired into pipeline)
)
if exist "src\stages\stage9_renderer\spec_renderer.py" (
    del /q "src\stages\stage9_renderer\spec_renderer.py"
    set /a KILLED+=1
    echo     Removed src\stages\stage9_renderer\spec_renderer.py (never imported)
)
if exist "src\vector_db" (
    rd /s /q "src\vector_db"
    set /a KILLED+=1
    echo     Removed src\vector_db\ (stage5 has its own ChromaDB init)
)
if exist "src\utils" (
    rd /s /q "src\utils"
    set /a KILLED+=1
    echo     Removed src\utils\ (empty)
)

:: -------------------------------------------------------
:: 6. Entire plugin system (never imported by app.py)
:: -------------------------------------------------------
echo   [6/7] Removing unused plugin system...
if exist "plugins" (
    rd /s /q "plugins"
    set /a KILLED+=1
    echo     Removed plugins\ (entire plugin system, 103K, never imported)
)
if exist "src\plugins" (
    rd /s /q "src\plugins"
    set /a KILLED+=1
    echo     Removed src\plugins\ (plugin base/loader/integration, never imported)
)

:: -------------------------------------------------------
:: 7. Duplicate ChromaDB data + dev artifacts
:: -------------------------------------------------------
echo   [7/7] Removing duplicate data and dev files...
if exist "chroma_data" (
    rd /s /q "chroma_data"
    set /a KILLED+=1
    echo     Removed chroma_data\ (duplicate of src\data\chroma_techniques\)
)
if exist "data" (
    rd /s /q "data"
    set /a KILLED+=1
    echo     Removed data\ (duplicate ChromaDB + 2-entry sample.json)
)
if exist "test_results" (
    rd /s /q "test_results"
    set /a KILLED+=1
    echo     Removed test_results\ (regenerate with run_tests.bat)
)
if exist "worklog.md" (
    del /q "worklog.md"
    set /a KILLED+=1
    echo     Removed worklog.md
)
if exist ".env" (
    del /q ".env"
    set /a KILLED+=1
    echo     Removed .env (code hardcodes localhost:11434)
)
if exist "pyproject.toml" (
    del /q "pyproject.toml"
    set /a KILLED+=1
    echo     Removed pyproject.toml (Poetry dev config, not needed to run)
)

:: -------------------------------------------------------
:: DONE
:: -------------------------------------------------------
echo.
echo ======================================================================
echo   CLEANUP COMPLETE
echo ======================================================================
echo.
echo   Removed !KILLED! items/groups.
echo.
echo   What remains (the actual app):
echo     src\gui\app.py              - Flask server
echo     src\gui\templates\index.html - GUI
echo     src\gui\static\logo.png     - Logo
echo     src\core\models.py          - Data models
echo     src\core\json_utils.py      - JSON extraction
echo     src\core\exceptions.py      - Custom exceptions
echo     src\models\ollama_client.py - Ollama wrapper
echo     src\models\embedding_client.py
echo     src\stages\stage1-9\        - All 9 pipeline stages
echo     src\data\chroma_techniques\ - ChromaDB technique store
echo     config\settings.yaml        - Config
echo     requirements.txt            - Dependencies
echo     run.bat                     - Server launcher
echo     launcher.py                 - Exe entry point
echo     scripts\test_battery.py     - Test suite
echo     run_tests.bat               - Test runner
echo.
echo   Run the app to verify:  run.bat
echo.
pause