"""
Adaptive Output Length system for Kirator Prompt Factory.

Generates multiple prompt variants at different verbosity levels:
  - Tiny:       ~500 tokens  — essential constraints only, maximal compression
  - Medium:     ~1500 tokens — balanced detail (default pipeline output)
  - Professional: ~3000 tokens — comprehensive with rationale
  - Enterprise:  ~5000+ tokens — exhaustive with examples, edge cases, verification

The Medium variant is produced by the normal compose() path.
Tiny/Professional/Enterprise are produced by re-prompting the LLM with
length-specific instructions.
"""

import logging
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

# ================================================================
# LENGTH PRESETS
# ================================================================

LENGTH_PRESETS = {
    "tiny": {
        "label": "Tiny",
        "target_tokens": 500,
        "description": "Essential constraints only — maximum compression",
        "instruction": (
            "Compose an EXTREMELY CONCISE version of this prompt. "
            "Target: ~500 tokens maximum.\n"
            "Rules:\n"
            "- Strip ALL non-essential text\n"
            "- Keep only: role (1 line), task (1-2 sentences), key constraints (bullet list)\n"
            "- No examples, no rationale, no meta-commentary\n"
            "- Every word must earn its place\n"
            "Return ONLY the compressed prompt."
        ),
    },
    "medium": {
        "label": "Medium",
        "target_tokens": 1500,
        "description": "Balanced detail — production-ready default",
        "instruction": (
            "Compose a balanced, production-ready prompt. "
            "Target: ~1500 tokens.\n"
            "Rules:\n"
            "- Clear role assignment\n"
            "- Well-structured task description\n"
            "- Key techniques applied naturally\n"
            "- Important constraints listed\n"
            "- Output format specified\n"
            "Return ONLY the prompt."
        ),
    },
    "professional": {
        "label": "Professional",
        "target_tokens": 3000,
        "description": "Comprehensive with rationale and edge cases",
        "instruction": (
            "Compose a COMPREHENSIVE professional-grade prompt. "
            "Target: ~3000 tokens.\n"
            "Rules:\n"
            "- Detailed role with expertise context\n"
            "- Thorough task breakdown with sub-objectives\n"
            "- Techniques applied with clear reasoning\n"
            "- Constraints with rationale for each\n"
            "- Edge cases and boundary conditions to consider\n"
            "- Quality expectations and success criteria\n"
            "- Clear output format with examples of expected structure\n"
            "Return ONLY the prompt."
        ),
    },
    "enterprise": {
        "label": "Enterprise",
        "target_tokens": 5000,
        "description": "Exhaustive with examples, verification steps, and full documentation",
        "instruction": (
            "Compose an EXHAUSTIVE enterprise-grade prompt. "
            "Target: ~5000+ tokens.\n"
            "Rules:\n"
            "- Expert role with detailed capability description\n"
            "- Complete task decomposition into numbered sub-tasks\n"
            "- Every technique fully explained with expected behavior\n"
            "- All constraints with detailed rationale and examples of violations\n"
            "- Edge cases, failure modes, and recovery strategies\n"
            "- Input/output schema examples\n"
            "- Step-by-step verification checklist\n"
            "- Performance and quality benchmarks\n"
            "- Security considerations\n"
            "- Documentation requirements for the output\n"
            "- Self-review instructions\n"
            "Return ONLY the prompt."
        ),
    },
}


def _extract_prompt(raw: str) -> str:
    """Strip LLM artifacts from the response."""
    text = raw.strip()
    text = re.sub(r"__(?:START|END)\s*THINKING__", "", text, flags=re.DOTALL)
    text = re.sub(r"```(?:prompt|markdown)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = re.sub(
        r"^(?:here is (?:the )?(?:an? )?(?:\w+\s+)?(?:version|prompt|prompt)[:\s]*,?\s*)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


class AdaptiveLengthComposer:
    """
    Generates prompt variants at different verbosity levels.

    Usage:
        alc = AdaptiveLengthComposer(llm_client)
        variants = alc.generate_variants(request, strategy, intent, difficulty)
        # variants = {"tiny": "...", "medium": "...", "professional": "...", "enterprise": "..."}
    """

    def __init__(self, llm):
        self.llm = llm

    def generate_variants(
        self,
        request: str,
        strategy,
        intent=None,
        difficulty=None,
        base_prompt: str = "",
        modes: list[str] | None = None,
    ) -> dict[str, dict]:
        """
        Generate prompt variants for the requested modes.

        Args:
            request: Original user request
            strategy: PromptStrategy from Stage 4
            intent: IntentAnalysis from Stage 2 (optional)
            difficulty: DifficultyAssessment from Stage 3 (optional)
            base_prompt: If provided, skip medium (use this as-is)
            modes: Which modes to generate. Default: ["tiny", "professional", "enterprise"]

        Returns:
            Dict of {mode: {"prompt": str, "char_count": int, "label": str}}
        """
        if modes is None:
            modes = ["tiny", "professional", "enterprise"]

        # Build common context for the LLM
        tech_names = []
        if hasattr(strategy, "selected_techniques"):
            tech_names = [t.name for t in strategy.selected_techniques]

        domain = "general"
        if intent and hasattr(intent, "domain_knowledge_required") and intent.domain_knowledge_required:
            domain = ", ".join(intent.domain_knowledge_required)

        system_prompt = (
            "You are a world-class prompt engineer. "
            "Your job is to craft a prompt that another LLM will receive. "
            "Return ONLY the prompt text itself. No explanation, no meta-commentary."
        )

        common_context = (
            f"## Original Task\n{request}\n\n"
            f"## Domain\n{domain}\n\n"
            f"## Techniques to incorporate\n{', '.join(tech_names)}\n\n"
        )

        if base_prompt and "medium" in modes:
            modes = [m for m in modes if m != "medium"]

        variants = {}

        # Medium: use base prompt if provided
        if base_prompt:
            variants["medium"] = {
                "prompt": base_prompt,
                "char_count": len(base_prompt),
                "label": "Medium",
            }

        for mode in modes:
            preset = LENGTH_PRESETS.get(mode)
            if not preset:
                continue

            user_prompt = (
                f"{common_context}"
                f"## Length Mode: {preset['label']} ({preset['target_tokens']} tokens)\n"
                f"{preset['description']}\n\n"
                f"{preset['instruction']}"
            )

            try:
                raw = self.llm.generate(user_prompt, system_prompt=system_prompt)
                cleaned = _extract_prompt(raw)
                variants[mode] = {
                    "prompt": cleaned,
                    "char_count": len(cleaned),
                    "label": preset["label"],
                }
                logger.info(f"[Adaptive] {preset['label']}: {len(cleaned)} chars")
            except Exception as e:
                logger.warning(f"[Adaptive] Failed to generate {mode}: {e}")
                variants[mode] = {
                    "prompt": f"[Failed to generate {preset['label']} variant: {e}]",
                    "char_count": 0,
                    "label": preset["label"],
                }

        return variants

    def auto_select_mode(self, difficulty=None, intent=None) -> str:
        """
        Auto-select the best output length based on task characteristics.

        Simple heuristic:
        - trivial/simple → tiny or medium
        - moderate → medium
        - complex → professional
        - expert → enterprise
        """
        if difficulty is None:
            return "medium"

        level = difficulty.overall_level.value if hasattr(difficulty, "overall_level") else "moderate"

        mapping = {
            "trivial": "tiny",
            "simple": "medium",
            "moderate": "medium",
            "complex": "professional",
            "expert": "enterprise",
        }
        return mapping.get(level, "medium")

    @staticmethod
    def get_available_modes() -> list[dict]:
        """Return info about all available length modes."""
        return [
            {
                "id": mode_id,
                "label": preset["label"],
                "target_tokens": preset["target_tokens"],
                "description": preset["description"],
            }
            for mode_id, preset in LENGTH_PRESETS.items()
        ]