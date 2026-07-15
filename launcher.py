"""
Kirator Prompt Intelligence - Launcher
Entry point for both development and packaged (.exe) builds.
Handles Ollama detection, model verification, and browser auto-open.
"""

import sys
import os
import threading
import webbrowser
import time


def get_base_path():
    """
    Get the base project path.
    When frozen (PyInstaller exe), use the exe's directory.
    When running as script, use the script's directory.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_model_name(model_entry):
    """
    Extract model name from various ollama response formats.
    Different versions of the ollama package return different structures.
    """
    # Dict format: {"name": "...", ...} or {"model": "...", ...}
    if isinstance(model_entry, dict):
        name = model_entry.get("name") or model_entry.get("model")
        if name:
            return name
    # Object format: model_entry.name
    if hasattr(model_entry, "name"):
        return model_entry.name
    if hasattr(model_entry, "model"):
        return model_entry.model
    # String format: just the name directly
    if isinstance(model_entry, str):
        return model_entry
    return None


def check_ollama_connection():
    """
    Check if Ollama is running at localhost:11434.
    Returns (is_connected: bool, model_names: list)
    """
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            model_names = []
            for m in models:
                name = get_model_name(m)
                if name:
                    model_names.append(name)
            return True, model_names
    except Exception:
        pass
    return False, []


def check_ollama_cli():
    """
    Check if the 'ollama' command is available (Ollama is installed).
    Returns True if 'ollama' is found in PATH.
    """
    try:
        result = os.popen("where ollama 2>nul").read()
        return len(result.strip()) > 0
    except Exception:
        return False


def model_available(model_names, target):
    """
    Check if a target model name (e.g. 'deepseek-r1:8b') is available.
    Handles tag variations like 'deepseek-r1:8b' vs 'deepseek-r1:latest'.
    """
    target_base = target.split(":")[0]
    for name in model_names:
        if name == target:
            return True
        name_base = name.split(":")[0]
        if name_base == target_base:
            return True
    return False


def open_browser_after_delay(port, delay=2):
    """Wait for the server to start, then open the default browser."""
    time.sleep(delay)
    webbrowser.open(f"http://127.0.0.1:{port}")


def main():
    PORT = 5000
    REQUIRED_MODELS = ["deepseek-r1:8b", "llama3.1:8b"]

    base_path = get_base_path()

    # When running as a frozen exe, add the base path to sys.path
    # so that 'from src.gui.app import app' still works
    if getattr(sys, 'frozen', False):
        sys.path.insert(0, base_path)

    print()
    print("=" * 62)
    print("    KIRATOR PROMPT INTELLIGENCE")
    print("    9-Stage AI Prompt Engineering Pipeline")
    print("=" * 62)
    print()

    # --- Step 1: Check Ollama is running ---
    print("  [1/3] Checking Ollama connection...", end=" ", flush=True)

    ollama_running, model_names = check_ollama_connection()

    if not ollama_running:
        print("NOT FOUND")
        print()
        print("  Ollama is not running or not installed.")
        print()

        ollama_installed = check_ollama_cli()

        if ollama_installed:
            print("  Ollama is installed but not running.")
            print("  Please open the Ollama application and try again.")
        else:
            print("  Ollama does not appear to be installed.")
            print()
            print("  To install Ollama:")
            print("    1. Go to https://ollama.com/download")
            print("    2. Download and install Ollama for Windows")
            print("    3. Open Ollama (it runs in your system tray)")
            print("    4. Open a command prompt and run:")
            for model in REQUIRED_MODELS:
                print(f"       ollama pull {model}")
            print()
            print("  Then run this application again.")

        print()
        print("  Press Enter to exit...")
        try:
            input()
        except Exception:
            pass
        sys.exit(1)

    print(f"CONNECTED  ({len(model_names)} model(s) found)")

    # --- Step 2: Check required models ---
    print("  [2/3] Checking required models...", end=" ", flush=True)

    missing = []
    for model in REQUIRED_MODELS:
        if not model_available(model_names, model):
            missing.append(model)

    if missing:
        print("MISSING")
        print()
        print(f"  The following models are required but not found:")
        for m in missing:
            print(f"    - {m}")
        print()
        print("  Open a command prompt and run:")
        for m in missing:
            print(f"    ollama pull {m}")
        print()
        print("  Then run this application again.")
        print()
        print("  Press Enter to exit...")
        try:
            input()
        except Exception:
            pass
        sys.exit(1)

    print("OK  (all models available)")

    # --- Step 3: Start the Flask app ---
    print("  [3/3] Starting server...", end=" ", flush=True)

    # Start browser opener in background thread
    browser_thread = threading.Thread(
        target=open_browser_after_delay,
        args=(PORT, 3),
        daemon=True
    )
    browser_thread.start()

    # Import and run the Flask application
    try:
        from src.gui.app import app
    except ImportError as e:
        print("FAILED")
        print()
        print(f"  Could not import the application: {e}")
        print(f"  Base path: {base_path}")
        print()
        print("  If you are running from source, make sure you are")
        print("  in the project root directory.")
        print()
        print("  Press Enter to exit...")
        try:
            input()
        except Exception:
            pass
        sys.exit(1)

    print(f"DONE")
    print()
    print("-" * 62)
    print(f"  Server running at: http://127.0.0.1:{PORT}")
    print("  Your browser should open automatically.")
    print("  If it doesn't, open the URL above manually.")
    print("  Press Ctrl+C to stop the server.")
    print("-" * 62)
    print()

    # Run the Flask app (this blocks until Ctrl+C)
    app.run(host="127.0.0.1", port=PORT, threaded=True)


if __name__ == "__main__":
    main()