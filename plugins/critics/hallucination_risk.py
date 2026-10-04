"""Sample critic plugin: hallucination risk detector."""

from __future__ import annotations

import re

from src.plugins.base import KiratorPlugin, kirator_plugin


@kirator_plugin(
    plugin_type="critic",
    plugin_id="critic_hallucination_risk",
    name="Hallucination Risk Detector",
    version="1.0.0",
    description="Flags vague / open-ended prompt patterns that raise hallucination risk.",
    author="Kirator Designs",
)
class HallucinationRiskCritic(KiratorPlugin):
    HIGH_RISK_PATTERNS = [
        (r"\b(explain|describe|tell me about)\b.*\b(anything|everything)\b", "Overly broad request"),
        (r"\b(give me|provide|list)\b.*\b(all|every)\b", "Universal quantifier"),
    ]

    MITIGATING_PATTERNS = [
        r"\b(source|citation|reference|url|link)\b",
        r"\b(according to|based on|from)\b",
        r"\b(verify|check|confirm)\b",
        r"\b(if unsure|i don't know|do not invent)\b",
    ]

    def activate(self):
        pass

    def deactivate(self):
        pass

    def evaluate(self, prompt_text: str, target_model: str = "generic"):
        lower = prompt_text.lower()
        risk_factors = []
        for pattern, description in self.HIGH_RISK_PATTERNS:
            if re.search(pattern, lower, re.MULTILINE):
                risk_factors.append(description)

        mitigations = [
            "Has hallucination mitigation"
            for pattern in self.MITIGATING_PATTERNS
            if re.search(pattern, lower, re.IGNORECASE)
        ]

        risk_score = len(risk_factors)
        if mitigations:
            risk_score = max(0, risk_score - 1)
        if re.search(r"\d+", prompt_text):
            risk_score = max(0, risk_score - 1)
        if re.search(r"[#\-*]", prompt_text):
            risk_score = max(0, risk_score - 1)

        if risk_score == 0:
            level = "low"
        elif risk_score <= 2:
            level = "medium"
        else:
            level = "high"

        return {
            "hallucination_risk": level,
            "risk_factors_found": risk_factors,
            "mitigations_found": mitigations,
            "risk_score": risk_score,
        }
