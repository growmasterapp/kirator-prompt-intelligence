"""Shared pytest fixtures for Kirator Prompt Intelligence."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


@pytest.fixture()
def project_root() -> Path:
    return ROOT


@pytest.fixture()
def tmp_history(tmp_path):
    from src.core.history_store import HistoryStore

    store = HistoryStore(path=tmp_path / "history.json", max_entries=20)
    return store


@pytest.fixture()
def flask_app(tmp_history, monkeypatch):
    """Flask app with an isolated PipelineService (no shared singleton bleed)."""
    from src.pipeline import service as pipeline_mod
    from src.pipeline.service import PipelineService

    isolated = PipelineService(history=tmp_history)
    monkeypatch.setattr(pipeline_mod, "_service", isolated)

    # Re-import app after patching singleton used by get_pipeline_service
    import importlib
    import src.gui.app as gui_app

    importlib.reload(gui_app)
    gui_app.pipeline = isolated
    gui_app.history = tmp_history
    gui_app.app.config["TESTING"] = True
    return gui_app.app


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture(scope="session")
def ollama_available() -> bool:
    try:
        import httpx

        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture()
def require_ollama(ollama_available):
    if not ollama_available:
        pytest.skip("Ollama is not running on localhost:11434")


@pytest.fixture(scope="session")
def live_server(ollama_available):
    """Start Flask on an ephemeral port for Playwright GUI tests."""
    import socket
    from werkzeug.serving import make_server

    # Bind a free port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    from src.gui.app import app

    app.config["TESTING"] = True
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Wait until responsive
    import httpx

    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            if httpx.get(f"{base}/api/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        server.shutdown()
        pytest.fail("Live Flask server failed to start")

    yield {"base_url": base, "port": port, "ollama": ollama_available}
    server.shutdown()
