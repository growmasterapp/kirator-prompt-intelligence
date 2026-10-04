"""Prompt Architect agent — wraps PipelineService for workspace-style use."""

from __future__ import annotations

from typing import Any

from src.pipeline.service import PipelineService, get_pipeline_service


class PromptArchitectAgent:
    """
    Product-facing agent for prompt improvement.

    Keeps GUI/CLI/future workspace panels talking to a stable interface
    while the pipeline implementation evolves underneath.
    """

    name = "Prompt Architect"
    description = "Routes, critiques, and optimizes prompts for a target model."

    def __init__(self, pipeline: PipelineService | None = None):
        self.pipeline = pipeline or get_pipeline_service()

    def improve(self, request_text: str, target_model: str = "generic") -> dict[str, Any]:
        """Start an improvement run (async via pipeline background worker)."""
        return self.pipeline.start(request_text, target_model)

    def status(self) -> dict[str, Any]:
        terminal = self.pipeline.consume_terminal()
        if terminal:
            return terminal
        return self.pipeline.snapshot()

    def cancel(self) -> dict[str, Any]:
        return self.pipeline.cancel()

    def info(self) -> dict[str, str]:
        return {
            "id": "prompt_architect",
            "name": self.name,
            "description": self.description,
        }
