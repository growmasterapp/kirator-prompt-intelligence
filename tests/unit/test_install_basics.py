"""Local secret key, port fallback, brand kit, and public version text."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.overnight]

OLD_SECRET = "kirator-gui-secret-v3"


def test_secret_key_is_random_and_reused(tmp_path):
    from src.core.secret_store import load_or_create_secret_key

    path = tmp_path / "secret_key"
    first = load_or_create_secret_key(path)
    second = load_or_create_secret_key(path)
    assert first == second
    assert len(first) >= 32
    assert first != OLD_SECRET
    assert OLD_SECRET not in path.read_text(encoding="utf-8") or first != OLD_SECRET


def test_source_does_not_hardcode_the_old_secret(project_root):
    app_src = (project_root / "src" / "gui" / "app.py").read_text(encoding="utf-8")
    assert OLD_SECRET not in app_src
    assert "load_or_create_secret_key" in app_src


def test_busy_port_uses_the_next_free_one():
    from src.core.ports import choose_listen_port

    held = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    held.bind(("127.0.0.1", 0))
    busy = held.getsockname()[1]
    try:
        chosen = choose_listen_port("127.0.0.1", busy, span=5)
    finally:
        held.close()
    assert chosen != busy
    assert busy < chosen <= busy + 4


def test_settings_version_port_and_fast_mode():
    from src.core.config import reload_settings

    reload_settings()
    settings = reload_settings()
    assert settings.project_version == "1.1.0"
    assert settings.server.port == 5070
    assert settings.server.port != 5000
    assert settings.pipeline.fast_mode is True


def test_readme_matches_settings_and_drops_purchase_wording(project_root):
    raw = yaml.safe_load((project_root / "config" / "settings.yaml").read_text(encoding="utf-8"))
    version = raw["project"]["version"]
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    readme_txt = (project_root / "README.txt").read_text(encoding="utf-8")
    license_text = (project_root / "LICENSE").read_text(encoding="utf-8")

    assert version in readme
    assert version in readme_txt
    assert "Start_Kirator_Prompt_InteL.bat" in readme
    assert "ollama pull deepseek-r1:8b" in readme
    assert "5070" in readme
    assert "one-time purchase" not in readme.lower()
    assert "one purchase" not in readme_txt.lower()
    assert "all rights reserved" in license_text.lower()
    assert "not licensed for redistribution" in license_text.lower()
    assert "permission is hereby granted" not in license_text.lower()


def test_missing_brand_kit_uses_builtin_mark(monkeypatch, tmp_path):
    from src.gui.brand import brand_kit_dir, logo_url, theme_url

    monkeypatch.delenv("KIRATOR_BRAND_KIT", raising=False)
    # The Windows kit path does not exist on this machine.
    assert brand_kit_dir() is None
    assert logo_url(tmp_path) == "/static/mark.svg"
    assert theme_url() is None


def test_brand_kit_is_optional_when_present(monkeypatch, tmp_path):
    from src.gui.brand import brand_kit_dir, brand_logo_file, logo_url, theme_url

    kit = tmp_path / "kit"
    kit.mkdir()
    (kit / "logo.png").write_bytes(b"\x89PNG\r\n" + b"x" * 16)
    (kit / "theme.css").write_text("/* kit */\n", encoding="utf-8")
    monkeypatch.setenv("KIRATOR_BRAND_KIT", str(kit))

    assert brand_kit_dir() == kit
    assert brand_logo_file() == kit / "logo.png"
    assert logo_url(tmp_path) == "/brand/logo"
    assert theme_url() == "/brand/theme.css"


def test_cancel_interrupts_a_blocking_model_call(monkeypatch):
    """Cancel must return while the model call is still blocked. No network."""
    from src.core.exceptions import PipelineCancelled
    from src.models.ollama_client import OllamaClient

    started = threading.Event()

    class FakeHttp:
        def close(self):
            self.closed = True

    class FakeOllama:
        def __init__(self, host=None, timeout=None):
            self._client = FakeHttp()

        def chat(self, model=None, messages=None):
            started.set()
            time.sleep(30)
            return {"message": {"content": "too late"}}

    monkeypatch.setattr("src.models.ollama_client.ollama.Client", FakeOllama)

    client = OllamaClient(
        base_url="http://127.0.0.1:9",
        default_model="fake",
        max_retries=0,
        timeout_seconds=5,
    )
    cancel_event = threading.Event()
    client.bind_cancel(cancel_event)
    box: dict = {}

    def _call():
        try:
            client.generate("hello", use_cache=False)
            box["error"] = None
        except PipelineCancelled as exc:
            box["error"] = exc

    worker = threading.Thread(target=_call, daemon=True)
    worker.start()
    assert started.wait(2)
    cancel_event.set()
    worker.join(3)
    assert not worker.is_alive()
    assert isinstance(box.get("error"), PipelineCancelled)
