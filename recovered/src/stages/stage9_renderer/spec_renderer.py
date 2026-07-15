"""
Spec Document Renderer — detailed breakdown output format for the Renderer stage.

Produces a comprehensive specification document showing the full
pipeline reasoning: classification, intent, difficulty, strategy,
technique selection, quality scores, and the final prompt.
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

NL = chr(10)


class SpecDocumentRenderer:
    """
    Renders the full pipeline output as a detailed specification document.

    This is the most verbose output format — designed for users who want
    to understand every decision the pipeline made and why.
    """

    def render(
        self,
        optimized_prompt: str,
        quality_report: dict,
        strategy,
        stats: dict,
        classification=None,
        intent=None,
        difficulty=None,
        techniques_found: list = None,
        memory_context: str = "",
    ) -> str:
        """Render the complete specification document."""
        lines = []

        lines.append("=" * 70)
        lines.append("  KIRATOR PROMPT SPECIFICATION DOCUMENT")
        lines.append("  Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("  Version: Kirator-v2.0")
        lines.append("=" * 70)
        lines.append("")

        # 1. ORIGINAL REQUEST
        lines.append("## 1. ORIGINAL REQUEST")
        lines.append("")
        request_text = stats.get("request", "N/A")
        lines.append(request_text)
        lines.append("")

        # 2. CLASSIFICATION (Stage 1)
        lines.append("## 2. REQUEST CLASSIFICATION (Stage 1 - Router)")
        lines.append("")
        if classification:
            lines.append(f"- **Category:** {self._val(classification, 'task_category')}")
            lines.append(f"- **Complexity:** {self._val(classification, 'complexity_level')}")
            lines.append(f"- **Confidence:** {self._val(classification, 'confidence_score')}")
            lines.append(f"- **Method:** {self._val(classification, 'reasoning_method')}")
        else:
            lines.append("*No classification data available*")
        lines.append("")

        # 3. INTENT ANALYSIS (Stage 2)
        lines.append("## 3. INTENT ANALYSIS (Stage 2)")
        lines.append("")
        if intent:
            lines.append(f"- **Primary Intent:** {self._val(intent, 'primary_intent')}")
            secondary = self._val(intent, 'secondary_intents', [])
            if secondary:
                lines.append(f"- **Secondary Intents:** {', '.join(secondary)}")
            domains = self._val(intent, 'domain_knowledge_required', [])
            if domains:
                lines.append(f"- **Domain Knowledge:** {', '.join(domains)}")
            constraints = self._val(intent, 'constraints_identified', [])
            if constraints:
                lines.append(f"- **Constraints Identified:** {', '.join(constraints)}")
            lines.append(f"- **Ambiguity Score:** {self._val(intent, 'ambiguity_score')}")
            lines.append(f"- **Confidence:** {self._val(intent, 'confidence')}")
        else:
            lines.append("*No intent data available*")
        lines.append("")

        # 4. DIFFICULTY ASSESSMENT (Stage 3)
        lines.append("## 4. DIFFICULTY ASSESSMENT (Stage 3)")
        lines.append("")
        if difficulty:
            lines.append(f"- **Overall Level:** {self._val(difficulty, 'overall_level')}")
            lines.append(f"- **Technical Complexity:** {self._val(difficulty, 'technical_complexity')}/10")
            lines.append(f"- **Domain Expertise:** {self._val(difficulty, 'domain_expertise_required')}/10")
            lines.append(f"- **Creativity Demand:** {self._val(difficulty, 'creativity_demand')}/10")
            lines.append(f"- **Estimated Steps:** {self._val(difficulty, 'estimated_steps')}")
            risks = self._val(difficulty, 'risk_factors', [])
            if risks:
                lines.append(f"- **Risk Factors:**")
                for r in risks:
                    lines.append(f"  - {r}")
        else:
            lines.append("*No difficulty data available*")
        lines.append("")

        # 5. STRATEGY (Stage 4)
        lines.append("## 5. PROMPT STRATEGY (Stage 4)")
        lines.append("")
        if strategy:
            lines.append(f"**Objective:** {self._val(strategy, 'objective_summary')}")
            lines.append("")
            techs = self._val(strategy, 'selected_techniques', [])
            if techs:
                lines.append("**Selected Techniques:**")
                for t in techs:
                    if isinstance(t, dict):
                        lines.append(f"  - **{t.get('name', '?')}** ({t.get('category', '?')}) - eff: {t.get('effectiveness_score', '?')}")
                    elif hasattr(t, 'name'):
                        lines.append(f"  - **{t.name}** ({t.category}) - eff: {t.effectiveness_score}")
                lines.append("")
            lines.append(f"**Reasoning Framework:** {self._val(strategy, 'reasoning_framework')}")
            lines.append(f"**Estimated Tokens:** ~{self._val(strategy, 'estimated_tokens')}")
            lines.append(f"**Strategy Confidence:** {self._val(strategy, 'confidence')}")
        else:
            lines.append("*No strategy data available*")
        lines.append("")

        # 6. TECHNIQUE SEARCH (Stage 5)
        lines.append("## 6. TECHNIQUE SEARCH RESULTS (Stage 5)")
        lines.append("")
        if techniques_found:
            for t in techniques_found:
                name = t.get("name", "?")
                cat = t.get("cat", "?")
                eff = t.get("eff", "?")
                lines.append(f"- **{name}** ({cat}, effectiveness: {eff})")
        else:
            lines.append("*No technique search data*")
        lines.append("")

        # 7. QUALITY REPORT (Stage 7-8)
        lines.append("## 7. QUALITY REPORT (Stage 7-8 - PEEM Framework)")
        lines.append("")
        if quality_report and isinstance(quality_report, dict):
            lines.append("| Axis | Score | Rationale |")
            lines.append("|------|-------|-----------|")
            axes = [
                ("Clarity / Structure", "clarity_structure"),
                ("Linguistic Quality", "linguistic_quality"),
                ("Fairness / Bias", "fairness_bias"),
                ("Completeness", "completeness"),
                ("Specificity", "specificity"),
                ("Ambiguity (lower=better)", "ambiguity"),
                ("Constraint Clarity", "constraint_clarity"),
                ("Model Compatibility", "model_compatibility"),
            ]
            rationale = quality_report.get("rationale", {})
            for label, key in axes:
                score = quality_report.get(key, "N/A")
                rat = rationale.get(key, "")
                lines.append(f"| {label} | {score}/5 | {rat} |")
            lines.append("")
            lines.append(f"**Overall Quality Score: {quality_report.get('overall_score', 'N/A')}/100**")
            lines.append("")
            weaknesses = quality_report.get("weaknesses", [])
            if weaknesses:
                lines.append("### Weaknesses Identified")
                for w in weaknesses:
                    lines.append(f"- {w}")
                lines.append("")
            improvements = quality_report.get("improvements", [])
            if improvements:
                lines.append("### Suggested Improvements")
                for imp in improvements:
                    lines.append(f"- {imp}")
                lines.append("")
        else:
            lines.append("*No quality report available*")
            lines.append("")

        # 8. FINAL OPTIMIZED PROMPT
        lines.append("## 8. FINAL OPTIMIZED PROMPT")
        lines.append("")
        lines.append("---")
        lines.append(optimized_prompt)
        lines.append("---")
        lines.append("")

        # 9. PROCESSING STATS
        lines.append("## 9. PROCESSING STATISTICS")
        lines.append("")
        if stats:
            for k, v in stats.items():
                lines.append(f"- **{k}:** {v}")
        lines.append("")

        # 10. MEMORY CONTEXT
        if memory_context:
            lines.append("## 10. CONVERSATION MEMORY CONTEXT")
            lines.append("")
            lines.append(memory_context)
            lines.append("")

        lines.append("---")
        lines.append(f"*Kirator Prompt Factory v2.0 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return NL.join(lines)

    @staticmethod
    def _val(obj, key, default="N/A"):
        """Safe attribute/dict access."""
        if obj is None:
            return default
        if isinstance(obj, dict):
            v = obj.get(key)
            if v is None:
                return default
            if hasattr(v, "value"):
                return v.value
            return v
        if hasattr(obj, key):
            v = getattr(obj, key)
            if hasattr(v, "value"):
                return v.value
            return v
        return default