"""Fast mode: trivial and simple requests skip the slow stages."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from src.core.history_store import HistoryStore
from src.core.models import (
    ComplexityLevel,
    DifficultyAssessment,
    IntentAnalysis,
    OutputFormat,
    PromptQualityScore,
    PromptStrategy,
    RequestClassification,
    TaskCategory,
    TechniqueMetadata,
)
from src.pipeline.fast_mode import should_use_fast_mode
from src.pipeline.service import PipelineService
from src.stages.stage1_router.router import RequestRouter

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


def test_hello_world_is_labeled_easy():
    """The phrase from the audit must be trivial or simple, with no model call."""
    router = RequestRouter(embedder=None)
    result = router.process("Write hello world in python", {})
    assert result.complexity_level in (ComplexityLevel.TRIVIAL, ComplexityLevel.SIMPLE)
    assert should_use_fast_mode(result, enabled=True) is True
    assert should_use_fast_mode(result, enabled=False) is False


def test_long_request_is_not_fast():
    text = (
        "Design a production microservice platform with kubernetes, docker, "
        "a message queue, real-time updates, and a load balancer for high concurrency. "
        "Include authentication, a database, monitoring, and a caching strategy."
    )
    router = RequestRouter(embedder=None)
    result = router.process(text, {})
    assert result.complexity_level not in (ComplexityLevel.TRIVIAL, ComplexityLevel.SIMPLE)
    assert should_use_fast_mode(result, enabled=True) is False


def _strategy() -> PromptStrategy:
    tech = TechniqueMetadata(
        id="role",
        name="Role",
        category="persona",
        description="Act as a helper",
        effectiveness_score=0.8,
        complexity_overhead=1,
        tags=["role"],
    )
    return PromptStrategy(
        objective_summary="say hello",
        selected_techniques=[tech],
        technique_ordering=["role"],
        reasoning_framework="direct",
        output_format_specification=OutputFormat.MARKDOWN,
        estimated_tokens=120,
        confidence=0.9,
    )


def _install_fakes(monkeypatch, level: ComplexityLevel, calls: dict, blocker=None):
    """Replace every stage with a local fake so the test never calls Ollama."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def bind_cancel(self, event):
            calls["cancel_event"] = event

        def abort(self):
            calls["aborted"] = True

    class FakeRouter:
        def __init__(self, embedder):
            pass

        def process(self, request, context):
            return RequestClassification(
                task_category=TaskCategory.CODE_GEN,
                complexity_level=level,
                confidence_score=0.9,
                reasoning_method="test",
                processing_time_ms=1.0,
            )

    class FakeIntent:
        def __init__(self, llm):
            pass

        def process(self, request, context):
            calls["s2"] += 1
            if blocker is not None:
                blocker["started"].set()
                event = calls.get("cancel_event")
                deadline = time.time() + 5
                while time.time() < deadline:
                    if event is not None and event.is_set():
                        from src.core.exceptions import PipelineCancelled

                        raise PipelineCancelled("stopped in test")
                    time.sleep(0.02)
                raise AssertionError("cancel was not noticed")
            return IntentAnalysis(
                primary_intent="code_generation",
                ambiguity_score=0.1,
                confidence=0.9,
            )

    class FakeDifficulty:
        def __init__(self, llm):
            pass

        def process(self, *args, **kwargs):
            calls["s3"] += 1
            return DifficultyAssessment(
                overall_level=ComplexityLevel.MODERATE,
                technical_complexity=5,
                domain_expertise_required=5,
                ambiguity_tolerance=5,
                creativity_demand=5,
                estimated_steps=3,
                confidence=0.5,
            )

    class FakeStrategy:
        def __init__(self, llm):
            pass

        def process(self, *args, **kwargs):
            calls["s4"] += 1
            return _strategy()

    class FakeTechniques:
        def __init__(self, embedder):
            pass

        def search(self, query, n):
            calls["s5"] += 1
            return []

    class FakeComposer:
        def __init__(self, llm, selector):
            pass

        def compose(self, *args, **kwargs):
            calls["s6"] += 1
            return "Write a Python program that prints hello world."

    class FakeCritic:
        def __init__(self, llm):
            pass

        def evaluate(self, prompt, target_model):
            calls["s7"] += 1
            return PromptQualityScore(overall_score=72, weaknesses=["short"], improvements=["add an example"])

    class FakeOptimizer:
        def __init__(self, llm):
            pass

        def optimize(self, *args, **kwargs):
            calls["s8"] += 1
            return {
                "optimized_prompt": "optimized",
                "final_score": 90,
                "iterations_used": 2,
                "converged": True,
                "quality_report": {"overall_score": 90, "weaknesses": [], "improvements": []},
            }

    class FakeRenderer:
        def render(self, *args, **kwargs):
            calls["s9"] += 1
            return "rendered prompt"

    monkeypatch.setattr("src.models.embedding_client.EmbeddingClient", FakeClient)
    monkeypatch.setattr("src.models.ollama_client.OllamaClient", FakeClient)
    monkeypatch.setattr("src.stages.stage1_router.router.RequestRouter", FakeRouter)
    monkeypatch.setattr("src.stages.stage2_intent_analyzer.analyzer.IntentAnalyzer", FakeIntent)
    monkeypatch.setattr("src.stages.stage3_difficulty_analyzer.analyzer.DifficultyAnalyzer", FakeDifficulty)
    monkeypatch.setattr("src.stages.stage4_strategy_planner.planner.StrategyPlanner", FakeStrategy)
    monkeypatch.setattr("src.stages.stage5_technique_selector.selector.TechniqueSelector", FakeTechniques)
    monkeypatch.setattr("src.stages.stage6_prompt_composer.composer.PromptComposer", FakeComposer)
    monkeypatch.setattr("src.stages.stage7_prompt_critic.critic.PromptCritic", FakeCritic)
    monkeypatch.setattr("src.stages.stage8_optimizer.optimizer.PromptOptimizer", FakeOptimizer)
    monkeypatch.setattr("src.stages.stage9_renderer.renderer.PromptRenderer", FakeRenderer)


def _service(tmp_path: Path) -> PipelineService:
    history = HistoryStore(path=tmp_path / "history.json")
    return PipelineService(history=history)


def test_fast_mode_skips_difficulty_and_optimizer(tmp_path, monkeypatch):
    calls = {"s2": 0, "s3": 0, "s4": 0, "s5": 0, "s6": 0, "s7": 0, "s8": 0, "s9": 0}
    _install_fakes(monkeypatch, ComplexityLevel.TRIVIAL, calls)
    service = _service(tmp_path)

    service._run("Write hello world in python", "generic")

    snap = service.snapshot()
    assert snap["status"] == "complete"
    assert snap["fast_mode"] is True
    assert calls["s3"] == 0
    assert calls["s8"] == 0
    assert calls["s2"] == 1
    assert calls["s6"] == 1
    assert calls["s7"] == 1
    assert calls["s9"] == 1
    assert snap["stages"]["3"]["state"] == "skipped"
    assert snap["stages"]["8"]["state"] == "skipped"
    assert snap["result"]["fast_mode"] is True
    assert snap["result"]["score"] == 72
    assert "hello world" in snap["result"]["prompt"].lower()


def test_full_mode_still_runs_difficulty_and_optimizer(tmp_path, monkeypatch):
    calls = {"s2": 0, "s3": 0, "s4": 0, "s5": 0, "s6": 0, "s7": 0, "s8": 0, "s9": 0}
    _install_fakes(monkeypatch, ComplexityLevel.COMPLEX, calls)
    service = _service(tmp_path)

    service._run("Design a large distributed system", "generic")

    snap = service.snapshot()
    assert snap["status"] == "complete"
    assert snap["fast_mode"] is False
    assert calls["s3"] == 1
    assert calls["s8"] == 1
    assert snap["result"]["score"] == 90
    assert snap["stages"]["3"]["state"] == "done"
    assert snap["stages"]["8"]["state"] == "done"


def test_cancel_stops_a_blocked_stage(tmp_path, monkeypatch):
    calls = {"s2": 0, "s3": 0, "s4": 0, "s5": 0, "s6": 0, "s7": 0, "s8": 0, "s9": 0}
    blocker = {"started": threading.Event()}
    _install_fakes(monkeypatch, ComplexityLevel.TRIVIAL, calls, blocker=blocker)
    service = _service(tmp_path)
    started = service.start("Write hello world in python", "generic")
    assert started["ok"] is True

    assert blocker["started"].wait(2)
    cancelled = service.cancel()
    assert cancelled["status"] == "cancel_requested"
    worker = service._worker
    assert worker is not None
    worker.join(3)
    assert not worker.is_alive()
    assert service.snapshot()["status"] == "cancelled"
