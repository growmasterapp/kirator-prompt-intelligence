"""Unit tests for the plugin loader and sample critic."""

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


def test_discover_and_activate_sample_plugin(project_root):
    from src.plugins.loader import PluginLoader
    from src.plugins.base import PluginType

    loader = PluginLoader(project_root=str(project_root))
    count = loader.discover()
    assert count >= 1
    activated = loader.load_all()
    assert activated >= 1

    critics = loader.get_active_plugins(PluginType.CRITIC)
    assert any(p.PLUGIN_ID == "critic_hallucination_risk" for p in critics)

    plugin = next(p for p in critics if p.PLUGIN_ID == "critic_hallucination_risk")
    result = plugin.evaluate("list everything about anything", "generic")
    assert isinstance(result, dict)
    assert "hallucination_risk" in result
