"""Unit tests for destination-model profiles."""

import pytest

from src.core.target_profiles import get_target_profile, list_target_profiles

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


def test_known_profiles():
    for key in ("generic", "chatgpt", "claude", "gemini", "grok", "llama", "deepseek", "mistral"):
        p = get_target_profile(key)
        assert p.id == key
        assert p.name
        assert p.hint


def test_unknown_falls_back_to_generic():
    p = get_target_profile("not-a-real-model")
    assert p.id == "generic"


def test_list_excludes_local_alias():
    ids = {p["id"] for p in list_target_profiles()}
    assert "chatgpt" in ids
    assert "local" not in ids
