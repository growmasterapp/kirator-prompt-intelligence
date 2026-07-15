"""
Reverse Prompt Engineering — analyze existing prompts.

Input:  Any prompt (from anywhere)
Output:
  - Intent extraction (what does this prompt try to do?)
  - Strengths analysis (what works well)
  - Weaknesses identification (what's missing or weak)
  - Missing constraints
  - Hallucination risk assessment
  - Improved version(s)
  - Minimal version (for comparison)
  - Professional enhancement

Reuses existing pipeline stages (S2 Intent, S3 Difficulty, S7 Critic)
and adds specialized reverse-engineering analysis.
"""

import json
import logging
import re
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.models import PromptQualityScore

logger = logging.getLogger(__name__)


def _clean_json(raw: str) -> str:
    """Clean LLM output and extract JSON."""
    text = raw.strip()
    text = re.sub(r"__(?:START|END)\s*THINKING__", "", text, flags=re.DOTALL)
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
        return json_str
    return text


class ReverseEngineer:
    """
    Analyzes an existing prompt and produces a comprehensive report
    with improvement suggestions and rewritten versions.
    """

    def __init__(self, reasoning_llm, composition_llm):
        self.reasoning = reasoning_llm
        self.composition = composition_llm

    def analyze(self, prompt_text: str) -> dict:
        """
        Full reverse engineering analysis.

        Returns dict with keys:
            intent_analysis, strengths, weaknesses, missing_constraints,
            hallucination_risk, techniques_detected, target_models,
            improved_version, minimal_version, professional_version,
            quality_score, processing_time
        """
        T = time.time()

        # Step 1: Intent extraction
        intent = self._extract_intent(prompt_text)

        # Step 2: Quality evaluation (reuse critic logic)
        quality = self._evaluate_quality(prompt_text)

        # Step 3: Comprehensive analysis (strengths, weaknesses, missing constraints)
        analysis = self._deep_analysis(prompt_text, intent, quality)

        # Step 4: Generate improved versions
        improved = self._generate_improved(prompt_text, analysis, "balanced")
        minimal = self._generate_improved(prompt_text, analysis, "minimal")
        professional = self._generate_improved(prompt_text, analysis, "professional")

        elapsed = round(time.time() - T, 1)

        return {
            "intent_analysis": intent,
            "quality_score": quality,
            "strengths": analysis.get("strengths", []),
            "weaknesses": analysis.get("weaknesses", []),
            "missing_constraints": analysis.get("missing_constraints", []),
            "hallucination_risk": analysis.get("hallucination_risk", {}),
            "techniques_detected": analysis.get("techniques_detected", []),
            "suggested_techniques": analysis.get("suggested_techniques", []),
            "improved_version": improved,
            "minimal_version": minimal,
            "professional_version": professional,
            "processing_time_sec": elapsed,
        }

    def _extract_intent(self, prompt_text: str) -> dict:
        """Extract what the prompt is trying to accomplish."""
        system_prompt = (
            "You are a prompt analyst. Analyze what this prompt is trying to accomplish. "
            "Return ONLY valid JSON, no markdown."
        )

        user_prompt = (
            'Analyze this prompt and return JSON:\n'
            '{"primary_goal": "main objective",\n'
            '"secondary_goals": ["list"],\n'
            '"target_audience": "who is meant to receive this prompt",\n'
            '"target_model": "which LLM this seems designed for (claude/gpt-4/gemini/local/unknown)",\n'
            '"domain": "subject area",\n'
            '"complexity_assessment": "simple/moderate/complex",\n'
            '"techniques_used": ["list of prompting techniques detected"]}\n\n'
            "PROMPT TO ANALYZE:\n" + prompt_text
        )

        try:
            raw = self.reasoning.generate(user_prompt, system_prompt=system_prompt)
            cleaned = _clean_json(raw)
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Intent extraction failed: {e}")
            return {"primary_goal": "unknown", "error": str(e)}

    def _evaluate_quality(self, prompt_text: str) -> dict:
        """Evaluate prompt quality using PEEM framework."""
        from src.stages.stage7_prompt_critic.critic import PromptCritic
        critic = PromptCritic(self.reasoning)
        score = critic.evaluate(prompt_text, "generic")
        return score.to_dict()

    def _deep_analysis(self, prompt_text: str, intent: dict, quality: dict) -> dict:
        """Comprehensive strength/weakness/constraint analysis."""
        system_prompt = (
            "You are an expert prompt engineer performing a deep analysis. "
            "Return ONLY valid JSON, no markdown."
        )

        user_prompt = (
            "Perform a deep analysis of this prompt. Return JSON:\n"
            '{"strengths": ["list of 3-5 things this prompt does well"],\n'
            '"weaknesses": ["list of 3-5 things that could be improved"],\n'
            '"missing_constraints": ["list of 2-4 constraints that should be added"],\n'
            '"hallucination_risk": {"level": "low/medium/high", "reasoning": "why"},\n'
            '"techniques_detected": ["list of techniques already present"],\n'
            '"suggested_techniques": ["list of techniques that should be added"]}\n\n'
            "PROMPT:\n" + prompt_text + "\n\n"
            "INTENT (from earlier analysis):\n" + json.dumps(intent, indent=2)
        )

        try:
            raw = self.reasoning.generate(user_prompt, system_prompt=system_prompt)
            cleaned = _clean_json(raw)
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Deep analysis failed: {e}")
            return {
                "strengths": ["Could not determine"],
                "weaknesses": ["Analysis failed: " + str(e)[:80]],
                "missing_constraints": [],
                "hallucination_risk": {"level": "unknown", "reasoning": str(e)[:100]},
                "techniques_detected": [],
                "suggested_techniques": [],
            }

    def _generate_improved(
        self, prompt_text: str, analysis: dict, mode: str = "balanced"
    ) -> str:
        """Generate an improved version of the prompt."""
        system_prompt = (
            "You are a world-class prompt engineer. "
            "Rewrite the given prompt to be significantly better. "
            "Return ONLY the improved prompt text. No explanation."
        )

        weaknesses = analysis.get("weaknesses", [])
        missing = analysis.get("missing_constraints", [])
        suggested = analysis.get("suggested_techniques", [])

        if mode == "minimal":
            instruction = (
                "Create a MINIMAL improved version — as short as possible while "
                "fixing the critical weaknesses. Target: under 200 words."
            )
        elif mode == "professional":
            instruction = (
                "Create a PROFESSIONAL-GRADE improved version — comprehensive, "
                "well-structured, with clear sections, edge case handling, "
                "and quality expectations. Target: 500-800 words."
            )
        else:
            instruction = (
                "Create a BALANCED improved version — clear, well-structured, "
                "fixing the identified weaknesses and adding missing constraints. "
                "Target: 200-400 words."
            )

        user_prompt = (
            f"IMPROVE THIS PROMPT ({mode.upper()} MODE)\n\n"
            f"{instruction}\n\n"
            f"Weaknesses to fix:\n"
            + "\n".join(f"- {w}" for w in weaknesses)
            + "\n\nMissing constraints to add:\n"
            + "\n".join(f"- {c}" for c in missing)
            + "\n\nTechniques to incorporate:\n"
            + ", ".join(suggested)
            + f"\n\nORIGINAL PROMPT:\n{prompt_text}"
        )

        try:
            raw = self.composition.generate(user_prompt, system_prompt=system_prompt)
            # Strip artifacts
            cleaned = raw.strip()
            cleaned = re.sub(r"__(?:START|END)\s*THINKING__", "", cleaned, flags=re.DOTALL)
            cleaned = re.sub(r"```(?:prompt|markdown)?\s*", "", cleaned)
            cleaned = re.sub(r"```\s*$", "", cleaned)
            cleaned = re.sub(
                r"^(?:here is (?:the )?(?:an? )?(?:improved|better|new)\s*(?:version|prompt|prompt)?[:\s]*)",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            return cleaned.strip()
        except Exception as e:
            logger.warning(f"Improved version generation failed ({mode}): {e}")
            return f"[Failed to generate {mode} version: {e}]"

    def get_stage_info(self) -> dict:
        return {"name": "Reverse Prompt Engineer", "stage": "R"}