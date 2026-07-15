"""
Model-Specific Prompt Profiles for Kirator Prompt Factory.

Different LLMs respond differently to the same prompt. This module provides
pre-configured profiles that adjust prompt construction based on the target model.

Each profile specifies:
  - Optimal system prompt style
  - Preferred technique adjustments
  - Known limitations to compensate for
  - Token context limits (for length tuning)
  - Output format preferences
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelProfile:
    """Configuration profile for a specific target LLM."""
    model_id: str
    display_name: str
    context_limit: int          # max context tokens
    optimal_prompt_length: int  # recommended prompt length in tokens

    # Technique adjustments: techniques that work especially well/poorly
    preferred_techniques: list[str] = field(default_factory=list)
    avoid_techniques: list[str] = field(default_factory=list)

    # Prompt style preferences
    prefers_markdown: bool = True
    prefers_numbered_steps: bool = True
    prefers_examples: bool = True
    max_examples: int = 3
    system_prompt_style: str = "direct"  # direct, conversational, formal

    # Known limitations the prompt should compensate for
    known_limitations: list[str] = field(default_factory=list)
    strength_notes: list[str] = field(default_factory=list)

    # Output tweaks
    output_format_hint: str = ""  # e.g. "Respond in valid JSON"
    temperature_guidance: str = "balanced"  # low, balanced, high

    def get_system_prompt_prefix(self) -> str:
        """Return a model-specific prefix for the system prompt."""
        if self.system_prompt_style == "conversational":
            return "Hey there! "
        elif self.system_prompt_style == "formal":
            return "You are instructed as follows. "
        return ""

    def get_length_adjustment(self) -> float:
        """Return a multiplier for prompt length (1.0 = normal)."""
        if self.context_limit <= 32768:
            return 0.8   # Compact for smaller context windows
        elif self.context_limit > 65536:
            return 1.2   # Can afford more detail
        return 1.0


# ================================================================
# MODEL PROFILES DATABASE
# ================================================================

MODEL_PROFILES: dict[str, ModelProfile] = {
    # --- LOCAL MODELS (Ollama) ---
    "deepseek-r1:8b": ModelProfile(
        model_id="deepseek-r1:8b",
        display_name="DeepSeek-R1 8B",
        context_limit=65536,
        optimal_prompt_length=2000,
        preferred_techniques=["cot", "reflection", "decompose", "verification"],
        avoid_techniques=["fewshot"],  # DeepSeek-R1's chain-of-thought IS the few-shot
        prefers_markdown=True,
        prefers_numbered_steps=True,
        prefers_examples=False,  # It reasons better without examples cluttering
        max_examples=1,
        system_prompt_style="direct",
        known_limitations=[
            "Tends to produce verbose internal reasoning that can pollute JSON output",
            "May add __START/END THINKING__ blocks",
            "Trailing commas in JSON output",
        ],
        strength_notes=[
            "Excellent at chain-of-thought reasoning",
            "Strong at self-reflection and error detection",
            "Good at following structured instructions when output format is explicit",
        ],
        output_format_hint="Return ONLY valid JSON. No thinking blocks, no markdown code fences.",
        temperature_guidance="low",
    ),
    "llama3.1:8b": ModelProfile(
        model_id="llama3.1:8b",
        display_name="Llama 3.1 8B",
        context_limit=128000,
        optimal_prompt_length=2500,
        preferred_techniques=["role", "fewshot", "constraints", "struct", "markdown"],
        avoid_techniques=[],
        prefers_markdown=True,
        prefers_numbered_steps=True,
        prefers_examples=True,
        max_examples=3,
        system_prompt_style="direct",
        known_limitations=[
            "8B parameter model may struggle with very complex multi-step reasoning",
            "Can be overly verbose in explanations",
        ],
        strength_notes=[
            "Excellent instruction following",
            "Strong at structured output (JSON, markdown)",
            "Good with role-playing and persona adoption",
            "128K context window allows for detailed prompts",
        ],
        output_format_hint="",
        temperature_guidance="balanced",
    ),
    "mistral:7b": ModelProfile(
        model_id="mistral:7b",
        display_name="Mistral 7B",
        context_limit=32768,
        optimal_prompt_length=1800,
        preferred_techniques=["role", "constraints", "fewshot"],
        avoid_techniques=["tot"],  # Tree-of-thought requires more capacity
        prefers_markdown=True,
        prefers_numbered_steps=False,
        prefers_examples=True,
        max_examples=2,
        system_prompt_style="direct",
        known_limitations=[
            "Smaller context window limits prompt complexity",
            "Less effective with abstract reasoning tasks",
        ],
        strength_notes=[
            "Very fast inference",
            "Good at following clear instructions",
            "Strong European language support",
        ],
        temperature_guidance="balanced",
    ),
    "codellama:7b": ModelProfile(
        model_id="codellama:7b",
        display_name="CodeLlama 7B",
        context_limit=16384,
        optimal_prompt_length=2000,
        preferred_techniques=["fewshot", "constraints", "decompose", "verification"],
        avoid_techniques=["creative", "style"],
        prefers_markdown=True,
        prefers_numbered_steps=True,
        prefers_examples=True,
        max_examples=3,
        system_prompt_style="direct",
        known_limitations=[
            "Specialized for code — weaker on non-code tasks",
            "16K context limits complex multi-file prompts",
        ],
        strength_notes=[
            "Excellent code generation and explanation",
            "Strong at code-specific few-shot learning",
            "Good at understanding code structure and patterns",
        ],
        output_format_hint="",
        temperature_guidance="low",
    ),
    "phi3:mini": ModelProfile(
        model_id="phi3:mini",
        display_name="Phi-3 Mini",
        context_limit=128000,
        optimal_prompt_length=1500,
        preferred_techniques=["role", "constraints", "fewshot"],
        avoid_techniques=["tot", "analogical"],
        prefers_markdown=True,
        prefers_numbered_steps=True,
        prefers_examples=True,
        max_examples=2,
        system_prompt_style="direct",
        known_limitations=[
            "Small model — complex reasoning may be shallow",
            "Can lose track of long instruction chains",
        ],
        strength_notes=[
            "Very efficient for its size",
            "Good instruction following for straightforward tasks",
            "Strong at structured Q&A format",
        ],
        temperature_guidance="balanced",
    ),
    # --- GENERIC FALLBACK ---
    "generic": ModelProfile(
        model_id="generic",
        display_name="Generic LLM",
        context_limit=65536,
        optimal_prompt_length=2000,
        preferred_techniques=["role", "constraints", "cot", "fewshot"],
        avoid_techniques=[],
        prefers_markdown=True,
        prefers_numbered_steps=True,
        prefers_examples=True,
        max_examples=3,
        system_prompt_style="direct",
        known_limitations=[],
        strength_notes=[],
        output_format_hint="",
        temperature_guidance="balanced",
    ),
}


class ModelProfileManager:
    """
    Manages model profiles and provides profile lookups.

    Usage:
        mgr = ModelProfileManager()
        profile = mgr.get_profile("deepseek-r1:8b")
        profile = mgr.get_profile("llama3.1:8b")
        profile = mgr.get_profile()  # returns generic fallback
    """

    def __init__(self, custom_profiles: dict[str, ModelProfile] = None):
        self._profiles = dict(MODEL_PROFILES)
        if custom_profiles:
            self._profiles.update(custom_profiles)

    def get_profile(self, model_id: str = "generic") -> ModelProfile:
        """Look up a model profile. Falls back to 'generic' if not found."""
        # Try exact match first
        if model_id in self._profiles:
            return self._profiles[model_id]

        # Try partial match (e.g. "deepseek-r1" matches "deepseek-r1:8b")
        model_lower = model_id.lower()
        for pid, profile in self._profiles.items():
            if model_lower in pid.lower() or pid.lower() in model_lower:
                return profile

        logger.warning(f"No profile found for '{model_id}', using generic fallback")
        return self._profiles["generic"]

    def get_all_profiles(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def get_profile_summary(self) -> list[dict]:
        return [
            {
                "model_id": p.model_id,
                "display_name": p.display_name,
                "context_limit": p.context_limit,
                "optimal_length": p.optimal_prompt_length,
                "preferred_techniques": p.preferred_techniques,
            }
            for p in self._profiles.values()
        ]

    def adjust_techniques_for_model(self, technique_ids: list[str], model_id: str = "generic") -> list[str]:
        """
        Adjust a list of technique IDs based on model preferences.

        - Adds preferred techniques if not already present
        - Removes avoided techniques
        - Returns the adjusted list
        """
        profile = self.get_profile(model_id)
        adjusted = list(technique_ids)

        # Remove avoided techniques
        adjusted = [t for t in adjusted if t not in profile.avoid_techniques]

        # Add preferred techniques (up to 2 that aren't already there)
        added = 0
        for pref in profile.preferred_techniques:
            if pref not in adjusted and added < 2:
                adjusted.append(pref)
                added += 1

        return adjusted