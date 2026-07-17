"""
Target-model profiles for prompt adaptation.

These describe the *destination* LLM the user will paste the optimized prompt into
(ChatGPT, Claude, etc.), not the local Ollama models that run the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetProfile:
    id: str
    name: str
    style: str = "markdown"
    hint: str = ""


TARGET_PROFILES: dict[str, TargetProfile] = {
    "generic": TargetProfile(
        id="generic",
        name="Generic LLM",
        style="markdown",
        hint="Clear structure, explicit constraints, portable formatting.",
    ),
    "chatgpt": TargetProfile(
        id="chatgpt",
        name="ChatGPT / GPT-4",
        style="markdown",
        hint="Use Markdown headers, explicit formatting instructions, JSON schema for structured output.",
    ),
    "claude": TargetProfile(
        id="claude",
        name="Claude / Anthropic",
        style="xml",
        hint="Use XML tags for structure (<thinking>, <output_format>). Prefer longer context with clear sections.",
    ),
    "gemini": TargetProfile(
        id="gemini",
        name="Gemini / Google",
        style="steps",
        hint="Include more examples (few-shot). Clear step-by-step instructions. Prefer concise but complete.",
    ),
    "grok": TargetProfile(
        id="grok",
        name="Grok / xAI",
        style="markdown",
        hint="Use Markdown formatting. Strong constraint listing. Clear role assignment.",
    ),
    "llama": TargetProfile(
        id="llama",
        name="Llama / Meta",
        style="simple",
        hint="Simpler structure. Clear role assignment. Moderate length to avoid context overflow.",
    ),
    "deepseek": TargetProfile(
        id="deepseek",
        name="DeepSeek",
        style="markdown",
        hint="Strong reasoning instructions. Prefer numbered steps and verification checks.",
    ),
    "mistral": TargetProfile(
        id="mistral",
        name="Mistral",
        style="markdown",
        hint="Concise instructions, clear constraints, limited nesting.",
    ),
    "local": TargetProfile(
        id="local",
        name="Local Model",
        style="simple",
        hint="Simpler structure. Clear role assignment. Moderate length to avoid context overflow.",
    ),
}


def get_target_profile(target_id: str | None) -> TargetProfile:
    if not target_id:
        return TARGET_PROFILES["generic"]
    key = target_id.strip().lower()
    return TARGET_PROFILES.get(key, TARGET_PROFILES["generic"])


def list_target_profiles() -> list[dict]:
    return [
        {"id": p.id, "name": p.name, "style": p.style, "hint": p.hint}
        for p in TARGET_PROFILES.values()
        if p.id != "local"  # keep local as alias, hide from primary picker
    ]
