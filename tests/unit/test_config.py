"""Unit tests for central configuration."""

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


def test_settings_load_defaults():
    from src.core.config import get_settings, reload_settings

    reload_settings()
    s = get_settings()
    assert s.project_name
    assert s.server.port > 0
    assert "ollama" in s.ollama.base_url or "11434" in s.ollama.base_url
    assert s.ollama.reasoning_model
    assert s.ollama.composition_model
    assert s.ollama.embedding_model == "bge-m3"


def test_project_root_points_to_repo(project_root):
    from src.core.config import project_root as pr

    root = pr()
    assert (root / "launcher.py").exists()
    assert (root / "config" / "settings.yaml").exists()
    assert root == project_root
