import logging
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.models import PromptQualityScore
from src.core.exceptions import reraise_if_cancelled
from src.core.json_utils import extract_json, parse_json_with_retry
from src.models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# 9 PEEM evaluation axes (build spec: 9 axes scored 1-5)
AXES = [
    "clarity_structure",
    "linguistic_quality",
    "fairness_bias",
    "completeness",
    "specificity",
    "ambiguity",
    "constraint_clarity",
    "model_compatibility",
    "overall_quality",
]

# Weights for computing the overall_quality axis as weighted average of sub-axes
SUB_AXIS_WEIGHTS = {
    "clarity_structure": 0.15,
    "linguistic_quality": 0.10,
    "fairness_bias": 0.10,
    "completeness": 0.15,
    "specificity": 0.15,
    "ambiguity": 0.10,
    "constraint_clarity": 0.10,
    "model_compatibility": 0.15,
}

# Sub-axes (first 8, used for weighted average calculation)
SUB_AXES = AXES[:8]

# Fuzzy key mapping: LLMs sometimes use slightly different key names.
# Maps common variants to the canonical axis name.
_FUZZY_KEY_MAP = {
    "clarity": "clarity_structure",
    "structure": "clarity_structure",
    "linguistic": "linguistic_quality",
    "language": "linguistic_quality",
    "grammar": "linguistic_quality",
    "fairness": "fairness_bias",
    "bias": "fairness_bias",
    "complete": "completeness",
    "specific": "specificity",
    "constraint": "constraint_clarity",
    "constraints": "constraint_clarity",
    "model_compat": "model_compatibility",
    "compatibility": "model_compatibility",
    "model_fit": "model_compatibility",
    "overall": "overall_quality",
    "quality": "overall_quality",
}


def _resolve_axis_key(raw_key: str) -> str | None:
    """Map a potentially non-standard axis key to the canonical name."""
    cleaned = raw_key.strip().lower().replace(" ", "_").replace("-", "_")
    # Exact match first
    if cleaned in AXES:
        return cleaned
    # Fuzzy match
    return _FUZZY_KEY_MAP.get(cleaned)


class PromptCritic:
    """Evaluates prompt quality using the PEEM framework (9 axes, 1-5 scale).

    The 9th axis (overall_quality) is computed as a weighted average of the
    8 sub-axes. The overall_score (0-100) is computed from all 9 axis scores
    for consistency.

    This critic works best with llama3.1:8b which produces cleaner JSON
    than deepseek-r1:8b. Pass a llama3.1:8b OllamaClient for best results.

    v2: Added LLM retry on JSON parse failure, fuzzy key matching,
    and more aggressive JSON repair.
    """

    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client

    def evaluate(self, prompt_text: str, target_model: str = "generic") -> PromptQualityScore:
        """Score a prompt on 9 axes and return a PromptQualityScore (Pydantic model)."""

        system_prompt = (
            "You are a prompt quality evaluator using the PEEM framework. "
            "You MUST return ONLY valid JSON with no other text, no markdown, no explanation. "
            "Rate each axis 1-5 where 5 is excellent."
        )

        user_prompt = (
            'Rate this prompt on 9 axes. Return ONLY this exact JSON structure:\n'
            '{"clarity_structure":{"score":1,"rationale":"x"},'
            '"linguistic_quality":{"score":1,"rationale":"x"},'
            '"fairness_bias":{"score":1,"rationale":"x"},'
            '"completeness":{"score":1,"rationale":"x"},'
            '"specificity":{"score":1,"rationale":"x"},'
            '"ambiguity":{"score":1,"rationale":"x"},'
            '"constraint_clarity":{"score":1,"rationale":"x"},'
            '"model_compatibility":{"score":1,"rationale":"x"},'
            '"overall_quality":{"score":1,"rationale":"x"},'
            '"weaknesses":["w1","w2"],'
            '"improvements":["i1","i2"]}\n\n'
            "PROMPT TO EVALUATE:\n"
            + prompt_text
            + "\n\nTARGET MODEL: "
            + target_model
        )

        # BUG 1 FIX: Try up to 3 LLM calls if JSON parsing fails
        max_llm_retries = 3
        last_error = None

        for llm_attempt in range(1, max_llm_retries + 1):
            try:
                # Disable cache on retries so we get a fresh response
                use_cache = (llm_attempt == 1)
                raw = self.llm.generate(user_prompt, system_prompt=system_prompt, use_cache=use_cache)

                # Use increasingly aggressive parsing
                retry_count = 3 if llm_attempt > 1 else 2
                data = parse_json_with_retry(raw, max_retries=retry_count)

                # Parse scores using fuzzy key matching
                scores = {}
                rationale = {}
                for raw_key, value in data.items():
                    resolved = _resolve_axis_key(raw_key)
                    if resolved and resolved in AXES:
                        if isinstance(value, dict):
                            scores[resolved] = int(value.get("score", 3))
                            rationale[resolved] = str(value.get("rationale", ""))
                        elif isinstance(value, (int, float)):
                            scores[resolved] = int(value)
                            rationale[resolved] = ""
                        # Clamp to 1-5
                        scores[resolved] = max(1, min(5, scores[resolved]))

                # Fill any missing axes with default 3
                for axis in AXES:
                    if axis not in scores:
                        scores[axis] = 3
                        rationale[axis] = ""

                # Compute overall_quality as weighted average of sub-axes
                weighted = sum(
                    scores.get(ax, 3) * SUB_AXIS_WEIGHTS[ax] for ax in SUB_AXES
                )
                computed_oq = max(1, min(5, round(weighted)))
                llm_oq = scores.get("overall_quality", 3)
                if llm_oq != 3:
                    scores["overall_quality"] = llm_oq
                else:
                    scores["overall_quality"] = computed_oq
                    rationale["overall_quality"] = "Computed as weighted average of sub-axes"

                # Compute overall_score (0-100) from all 9 axis scores
                sum_scores = sum(scores.get(axis, 3) for axis in AXES)
                overall = round((sum_scores / (len(AXES) * 5)) * 100)
                overall = max(0, min(100, overall))

                return PromptQualityScore(
                    clarity_structure=scores["clarity_structure"],
                    linguistic_quality=scores["linguistic_quality"],
                    fairness_bias=scores["fairness_bias"],
                    completeness=scores["completeness"],
                    specificity=scores["specificity"],
                    ambiguity=scores["ambiguity"],
                    constraint_clarity=scores["constraint_clarity"],
                    model_compatibility=scores["model_compatibility"],
                    overall_quality=scores["overall_quality"],
                    overall_score=overall,
                    weaknesses=data.get("weaknesses", []),
                    improvements=data.get("improvements", []),
                    rationale=rationale,
                )

            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                last_error = e
                logger.warning(
                    f"Critic JSON parse failed (LLM attempt {llm_attempt}/{max_llm_retries}): {e}"
                )
            except Exception as e:
                reraise_if_cancelled(e)
                last_error = e
                logger.error(
                    f"Critic evaluation error (LLM attempt {llm_attempt}/{max_llm_retries}): {e}"
                )

        # All LLM retries exhausted — return fallback
        logger.error(f"Critic: all {max_llm_retries} LLM attempts failed, returning fallback 50/100")
        return PromptQualityScore.fallback()

    def get_stage_info(self) -> dict:
        return {"name": "Prompt Critic (PEEM)", "stage": 7}