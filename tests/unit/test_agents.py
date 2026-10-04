"""Unit tests for agent façades."""

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


def test_prompt_architect_info(tmp_history, monkeypatch):
    from src.agents.prompt_architect import PromptArchitectAgent
    from src.pipeline.service import PipelineService
    import src.pipeline.service as pipeline_mod

    svc = PipelineService(history=tmp_history)
    monkeypatch.setattr(pipeline_mod, "_service", svc)

    agent = PromptArchitectAgent(pipeline=svc)
    info = agent.info()
    assert info["id"] == "prompt_architect"
    assert "Architect" in info["name"]


def test_prompt_architect_rejects_empty(tmp_history):
    from src.agents.prompt_architect import PromptArchitectAgent
    from src.pipeline.service import PipelineService

    agent = PromptArchitectAgent(pipeline=PipelineService(history=tmp_history))
    result = agent.improve("   ")
    assert result["ok"] is False
