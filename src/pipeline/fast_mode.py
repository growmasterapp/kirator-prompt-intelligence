"""
Fast mode — skip the slow stages for easy requests.

The router already labels each request trivial, simple, moderate, complex,
or expert. A full run of "Write hello world in python" used to take minutes
because stage 3 (difficulty) and stage 8 (optimizer) each call the local
model again. For trivial and simple requests those calls add little, so
fast mode skips them.

Turn this off in config/settings.yaml with pipeline.fast_mode: false.
"""

from __future__ import annotations

from src.core.models import (
    ComplexityLevel,
    DifficultyAssessment,
    PromptQualityScore,
    RequestClassification,
)

# Stages the audit called out as too heavy for an easy request.
SKIPPED_IN_FAST_MODE = (3, 8)

_FAST_LEVELS = {ComplexityLevel.TRIVIAL, ComplexityLevel.SIMPLE}


def should_use_fast_mode(classification: RequestClassification, enabled: bool = True) -> bool:
    """True when settings allow it and the router called the request easy."""
    if not enabled:
        return False
    return classification.complexity_level in _FAST_LEVELS


def difficulty_from_router(classification: RequestClassification) -> DifficultyAssessment:
    """
    A local stand-in for stage 3.

    The router already judged the difficulty. We reuse that label so later
    stages still receive a DifficultyAssessment, without another model call.
    """
    level = classification.complexity_level
    if level == ComplexityLevel.TRIVIAL:
        technical = 2
        steps = 1
        creativity = 2
    else:
        # simple
        technical = 3
        steps = 2
        creativity = 3

    confidence = classification.confidence_score
    if confidence < 0 or confidence > 1:
        confidence = 0.8

    return DifficultyAssessment(
        overall_level=level,
        technical_complexity=technical,
        domain_expertise_required=technical,
        ambiguity_tolerance=3,
        creativity_demand=creativity,
        estimated_steps=steps,
        risk_factors=[],
        confidence=confidence,
    )


def result_without_optimizer(prompt_text: str, quality: PromptQualityScore) -> dict:
    """
    The same shape stage 8 returns, using the critic score as-is.

    Fast mode does not rewrite the prompt. The composed prompt and the
    stage-7 score are the result.
    """
    return {
        "optimized_prompt": prompt_text,
        "final_score": quality.overall_score,
        "iterations_used": 0,
        "converged": True,
        "history": [],
        "quality_report": quality.to_dict(),
        "skipped": True,
    }
