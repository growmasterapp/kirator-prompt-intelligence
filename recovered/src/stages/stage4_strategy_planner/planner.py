"""
Stage 4: Strategy Planner

Creates a Prompt Specification Document (blueprint) that guides
the Composer stage. Uses DeepSeek-R1 for semantic understanding
of what techniques and structure the final prompt needs.
"""

import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.models import PromptStrategy, TechniqueMetadata, OutputFormat
from src.core.json_utils import extract_json, parse_json_with_retry
from src.models.ollama_client import OllamaClient
from src.stages.stage5_technique_selector.selector import TECHNIQUE_CATALOG

logger = logging.getLogger(__name__)

FMT_MAP = {
    "plain_text": OutputFormat.PLAIN_TEXT,
    "markdown": OutputFormat.MARKDOWN,
    "json": OutputFormat.JSON,
}

# Build a quick lookup from the tuple catalog
_CATALOG_DICT = {}
for item in TECHNIQUE_CATALOG:
    tech_id, name, category, description, tags, effectiveness = item
    _CATALOG_DICT[tech_id] = {
        "id": tech_id,
        "name": name,
        "category": category,
        "description": description,
        "effectiveness_score": effectiveness,
        "complexity_overhead": 1 if category in ("formatting", "persona", "control") else 2,
        "tags": tags,
    }

ALL_TECH_IDS = list(_CATALOG_DICT.keys())


def _extract_tech_id(raw) -> str | None:
    """Normalize a technique reference to a known catalog ID."""
    if isinstance(raw, str):
        cleaned = raw.strip().lower()
        # Direct ID match
        if cleaned in _CATALOG_DICT:
            return cleaned
        # Partial name match
        for tid, t in _CATALOG_DICT.items():
            if cleaned in t["name"].lower() or t["name"].lower() in cleaned:
                return tid
        return None
    if isinstance(raw, dict):
        return raw.get("id") or _extract_tech_id(raw.get("name", ""))
    return None


def _make_technique_metadata(tech_id: str) -> TechniqueMetadata | None:
    """Convert a catalog dict entry to a TechniqueMetadata Pydantic model."""
    t = _CATALOG_DICT.get(tech_id)
    if not t:
        return None
    return TechniqueMetadata(
        id=t["id"],
        name=t["name"],
        category=t["category"],
        description=t["description"],
        effectiveness_score=t["effectiveness_score"],
        complexity_overhead=t["complexity_overhead"],
        tags=t["tags"],
    )


class StrategyPlanner:
    """Creates a prompt strategy specification from classification + intent + difficulty."""

    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client

    def process(
        self,
        request: str,
        context: dict,
        classification=None,
        intent=None,
        difficulty=None,
    ) -> PromptStrategy:
        """
        Generate a strategy by asking the LLM which techniques to use,
        then resolving them against the full 24-technique catalog.
        """

        intent_str = intent.primary_intent if intent else "unknown"
        domain_str = (
            ", ".join(intent.domain_knowledge_required)
            if intent and intent.domain_knowledge_required
            else "general"
        )
        diff_str = difficulty.overall_level.value if difficulty else "moderate"
        tech_score = difficulty.technical_complexity if difficulty else 5
        creativity = difficulty.creativity_demand if difficulty else 5

        # Build available techniques list for the LLM
        tech_list_str = ", ".join(ALL_TECH_IDS)

        system_prompt = (
            "You are a prompt engineering strategist. "
            "Analyze the task and select the best techniques. "
            "Return ONLY valid JSON, no markdown, no explanation."
        )

        user_prompt = (
            "Create a prompt strategy for this task. Return ONLY JSON:\n"
            '{"objective_summary": "what the final prompt should accomplish",\n'
            '"techniques": ["pick 2-5 technique IDs from this list: '
            + tech_list_str
            + '"],\n'
            '"technique_ordering": ["order they should be applied as IDs"],\n'
            '"reasoning_framework": "analytical|creative|mixed",\n'
            '"output_format": "plain_text|markdown|json",\n'
            '"estimated_tokens": integer}\n\n'
            "TASK: " + request + "\n"
            "INTENT: " + intent_str + "\n"
            "DOMAIN: " + domain_str + "\n"
            "DIFFICULTY: " + diff_str + "\n"
            "TECHNICAL_SCORE: " + str(tech_score) + "/10\n"
            "CREATIVITY_DEMAND: " + str(creativity) + "/10"
        )

        try:
            raw = self.llm.generate(user_prompt, system_prompt=system_prompt)
            data = parse_json_with_retry(raw, max_retries=1)

            # Resolve technique IDs to catalog entries
            raw_techs = data.get("techniques", [])
            resolved_techs = []
            for t in raw_techs:
                tid = _extract_tech_id(t)
                if tid:
                    meta = _make_technique_metadata(tid)
                    if meta:
                        resolved_techs.append(meta)

            # Fallback if nothing resolved
            if not resolved_techs:
                resolved_techs = [_make_technique_metadata("cot"), _make_technique_metadata("role")]
                resolved_techs = [t for t in resolved_techs if t]

            # Resolve ordering
            raw_ordering = data.get("technique_ordering", [])
            clean_ordering = []
            for x in raw_ordering:
                tid = _extract_tech_id(x)
                if tid:
                    clean_ordering.append(tid)

            fmt_name = data.get("output_format", "markdown")
            tokens = int(data.get("estimated_tokens", 500))

            return PromptStrategy(
                objective_summary=data.get("objective_summary", request[:150]),
                selected_techniques=resolved_techs,
                technique_ordering=clean_ordering,
                reasoning_framework=data.get("reasoning_framework", "analytical"),
                output_format_specification=FMT_MAP.get(fmt_name, OutputFormat.MARKDOWN),
                quality_targets={},
                risk_mitigations=[],
                estimated_tokens=max(100, tokens),
                confidence=0.85,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Strategy parsing failed ({e}), using fallback")
        except Exception as e:
            logger.error(f"Strategy planning failed: {e}")

        # Graceful fallback
        return self._fallback_strategy(request)

    @staticmethod
    def _fallback_strategy(request: str) -> PromptStrategy:
        """Safe default when LLM strategy generation fails."""
        cot = _make_technique_metadata("cot")
        role = _make_technique_metadata("role")
        return PromptStrategy(
            objective_summary=request[:150],
            selected_techniques=[t for t in [cot, role] if t],
            technique_ordering=["cot", "role"],
            reasoning_framework="analytical",
            output_format_specification=OutputFormat.MARKDOWN,
            quality_targets={},
            risk_mitigations=[],
            estimated_tokens=300,
            confidence=0.6,
        )

    def get_stage_info(self) -> dict:
        return {"name": "Strategy Planner", "stage": 4}