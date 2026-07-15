"""
Sample Critic Plugin: Hallucination Risk Detector

Adds a specialized evaluation axis that assesses how likely
the prompt is to cause the model to hallucinate or fabricate information.
"""

import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.plugins.base import KiratorPlugin, kirator_plugin


@kirator_plugin(
    plugin_type="critic",
    plugin_id="critic_hallucination_risk",
    name="Hallucination Risk Detector",
    version="1.0.0",
    description="Evaluates prompts for hallucination risk factors: vague references, missing sources, open-ended claims.",
    author="Kirator Team",
)
class HallucinationRiskCritic(KiratorPlugin):

    # Patterns that increase hallucination risk
    HIGH_RISK_PATTERNS = [
        (r"\b(explain|describe|tell me about)\b.*\b(anything|everything)\b", "Overly broad request"),
        (r"\bwhat (is|are|was|were)\b(?!\s+(the|a|this|that)\s+\w+)", "Vague 'what is' without specific referent"),
        (r"\b(give me|provide|list)\b.*\b(all|every|any)\b", "Universal quantifier"),
        (r"^(?!\s*[#\-].{0,50}$)(?!.*\b(because|since|due to)\b).{0,200}$", "Very short prompt (< 30 chars) with no context"),
    ]

    MITIGATING_PATTERNS = [
        r"\b(source|citation|reference|URL|link)\b",
        r"\b(according to|based on|from)\b",
        r"\b(if (you|you're) (don't|are not|aren't) sure)\b",
        r"\b(verify|check|confirm)\b",
        r"\b(IIDM|refuse)\b",  # "I don't know" / "I am not sure" / "refuse"
    ]

    def activate(self):
        pass

    def deactivate(self):
        pass

    def evaluate(self, prompt_text: str, target_model: str = "generic"):
        """Evaluate hallucination risk. Returns dict or None to defer to default critic."""
        lower = prompt_text.lower()
        risk_factors = []
        mitigations = []

        # Check high-risk patterns
        for pattern, description in self.HIGH_RISK_PATTERNS:
            if re.search(pattern, lower, re.MULTILINE):
                risk_factors.append(description)

        # Check mitigating patterns
        for pattern in self.MITIGATING_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                mitigations.append("Has hallucination mitigation")

        # Check for specificity indicators
        has_specifics = bool(re.search(r"\d+", prompt_text))  # Has numbers
        has_structure = bool(re.search(r"[#\-*]", prompt_text))  # Has markdown structure

        # Calculate risk level
        risk_score = len(risk_factors)
        if mitigations:
            risk_score = max(0, risk_score - 1)
        if has_specifics:
            risk_score = max(0, risk_score - 1)
        if has_structure:
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