"""
Stage 6: Prompt Composer

Generates the final optimized prompt by combining:
- Strategy specification (from Stage 4)
- Selected techniques (from Stage 4/5)
- Classification context (from Stage 1/2/3)
- LLM-powered composition for intelligent prompt assembly

Has two modes:
  1. LLM composition (primary) -- uses llama3.1 to craft the prompt
  2. Template composition (fallback) -- assembles from technique templates

v2: Added anti-hallucination constraints (BUG 2 fix) and token budget awareness (BUG 6 fix).
"""

import sys
import os
import logging
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.stages.stage5_technique_selector.selector import TechniqueSelector

logger = logging.getLogger(__name__)


def _extract_prompt(raw: str) -> str:
    """Strip DeepSeek/LLM artifacts and extract clean prompt text."""
    text = raw.strip()
    # Remove thinking blocks
    text = re.sub(r"__(?:START|END) THINKING__", "", text, flags=re.DOTALL)
    text = re.sub(r"__[A-Z\s]+__", "", text)
    # Remove "Here is the prompt:" type prefixes
    text = re.sub(
        r"^(?:here is (?:the )?(?:an? )?(?:optimized |improved )?(?:prompt|version)[:\s]*,?\s*)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove trailing meta-commentary
    text = re.sub(
        r"\n*(?:note:|explanation:|this prompt|let me know if).*$",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return text.strip()


# ================================================================
# TECHNIQUE TEMPLATES
# Maps technique IDs to prompt section templates
# ================================================================

TECHNIQUE_TEMPLATES = {
    "cot": (
        "# REASONING INSTRUCTIONS\n"
        "Think step-by-step. Break this problem down into clear, logical steps. "
        "Show your reasoning at each stage before arriving at the final answer."
    ),
    "tot": (
        "# REASONING INSTRUCTIONS\n"
        "Consider multiple approaches to this problem. For each approach:\n"
        "1. Outline the approach briefly\n"
        "2. Evaluate its strengths and weaknesses\n"
        "3. Select the best approach and proceed with it"
    ),
    "fewshot": (
        "# EXAMPLES\n"
        "Follow the pattern demonstrated in the examples below. "
        "Match the format, style, and level of detail shown."
    ),
    "zeroshot": (
        "# INSTRUCTIONS\n"
        "Follow the instructions precisely. Use your knowledge to complete this task directly."
    ),
    "cot_fewshot": (
        "# INSTRUCTIONS\n"
        "For each example below, show your step-by-step reasoning before providing the answer. "
        "Then apply the same reasoning pattern to the task."
    ),
    "role": (
        "# ROLE\n"
        "You are a {domain} expert with deep experience in this field. "
        "Draw on specialized knowledge to provide accurate, authoritative guidance."
    ),
    "audience": (
        "# AUDIENCE\n"
        "Tailor your response for a {audience} reader. "
        "Adjust vocabulary, assumed knowledge, and level of detail accordingly."
    ),
    "struct": (
        "# OUTPUT FORMAT\n"
        "Your response MUST be in this exact format:\n{format_spec}\n"
        "Do not include any text outside this structure."
    ),
    "markdown": (
        "# OUTPUT FORMAT\n"
        "Format your response using Markdown with clear headers (##, ###), "
        "bullet points, and code blocks where appropriate."
    ),
    "constraints": (
        "# CONSTRAINTS\n"
        "- You MUST: {must_haves}\n"
        "- You MUST NOT: {must_avoids}\n"
        "Violating any constraint makes the response invalid."
    ),
    "negative": (
        "# THINGS TO AVOID\n"
        "Do NOT do any of the following:\n{negatives}"
    ),
    "length": (
        "# LENGTH\n"
        "Your response should be approximately {length_spec}. "
        "Be {verbosity} -- {verbosity_detail}."
    ),
    "decompose": (
        "# APPROACH\n"
        "Break this task into sub-tasks and address each one sequentially. "
        "Label each sub-task clearly before addressing it."
    ),
    "plan_execute": (
        "# APPROACH\n"
        "First, create a brief plan or outline. Then execute each step of the plan in order. "
        "Mark each step as complete before moving to the next."
    ),
    "verification": (
        "# QUALITY CHECK\n"
        "After completing your response, verify that:\n"
        "1. All requirements from the task are addressed\n"
        "2. The output is complete and correct\n"
        "3. No constraints have been violated"
    ),
    "iteration": (
        "# REFINEMENT\n"
        "Provide an initial response, then briefly review it and note any improvements "
        "you would make. Your final answer should incorporate those improvements."
    ),
    "edge_cases": (
        "# EDGE CASES\n"
        "Before answering, consider edge cases and unusual scenarios:\n"
        "- What inputs could break this?\n"
        "- What boundary conditions exist?\n"
        "- What assumptions might not hold?\n"
        "Address these in your response."
    ),
    "reflection": (
        "# SELF-CHECK\n"
        "Before giving your final answer, review your reasoning for:\n"
        "- Logical consistency\n"
        "- Completeness\n"
        "- Potential errors or misconceptions"
    ),
    "socratic": (
        "# ANALYSIS METHOD\n"
        "Before answering directly, consider:\n"
        "- What assumptions underlie this question?\n"
        "- What are the key factors to examine?\n"
        "- Are there alternative interpretations?\n"
        "Address these in your analysis."
    ),
    "creative": (
        "# CREATIVE DIRECTION\n"
        "Approach this with creative thinking. Explore innovative possibilities. "
        "Don't limit yourself to obvious or conventional approaches."
    ),
    "style": (
        "# STYLE\n"
        "Write in a {style} style. Maintain this tone consistently throughout your response."
    ),
    "security": (
        "# SECURITY\n"
        "- Never output real PII, credentials, or sensitive data\n"
        "- Sanitize all user inputs in code examples\n"
        "- Follow security best practices (OWASP, etc.)"
    ),
    "meta_prompt": (
        "# META\n"
        "Think about what makes an excellent prompt for this task. "
        "Consider what information the model needs, what constraints prevent bad outputs, "
        "and what structure produces the best results."
    ),
}


class PromptComposer:
    """
    Composes the final optimized prompt.

    Primary mode: sends context to the LLM and receives a crafted prompt.
    Fallback mode: assembles from technique templates.
    """

    def __init__(self, llm, selector: TechniqueSelector):
        self.llm = llm
        self.selector = selector

    def compose(self, request, strategy, classification, intent, difficulty):
        """
        Compose a prompt using the LLM (primary) or templates (fallback).

        Args:
            request: Original user request text
            strategy: PromptStrategy from Stage 4
            classification: RequestClassification from Stage 1
            intent: IntentAnalysis from Stage 2
            difficulty: DifficultyAssessment from Stage 3

        Returns:
            str: The composed prompt text
        """
        # Try LLM composition first
        try:
            result = self._compose_with_llm(request, strategy, intent, difficulty)
            if result and len(result) > 50:
                return result
        except Exception as e:
            logger.warning(f"LLM composition failed, using template fallback: {e}")

        # Fallback to template-based composition
        return self._compose_from_templates(request, strategy, intent, difficulty)

    def _compose_with_llm(self, request, strategy, intent, difficulty) -> str:
        """Use the LLM to intelligently compose the prompt."""

        # Gather technique info
        technique_descriptions = []
        technique_names = []
        for tech in strategy.selected_techniques:
            name = tech.name if hasattr(tech, "name") else tech.get("name", "unknown")
            desc = tech.description if hasattr(tech, "description") else tech.get("description", "")
            cat = tech.category if hasattr(tech, "category") else tech.get("category", "")
            technique_descriptions.append(f"- {name} ({cat}): {desc}")
            technique_names.append(name)

        tech_block = "\n".join(technique_descriptions)

        # Gather constraints
        constraints = []
        if difficulty and hasattr(difficulty, "risk_factors") and difficulty.risk_factors:
            constraints.extend([f"Avoid: {r}" for r in difficulty.risk_factors])
        if intent and hasattr(intent, "constraints_identified") and intent.constraints_identified:
            constraints.extend(intent.constraints_identified)

        constraint_block = "\n".join(f"- {c}" for c in constraints) if constraints else "None specified"

        # Domain context
        domain = "general"
        if intent and hasattr(intent, "domain_knowledge_required") and intent.domain_knowledge_required:
            domain = ", ".join(intent.domain_knowledge_required)

        # Difficulty context
        diff_level = "moderate"
        tech_score = 5
        if difficulty:
            diff_level = difficulty.overall_level.value if hasattr(difficulty, "overall_level") else "moderate"
            tech_score = difficulty.technical_complexity if hasattr(difficulty, "technical_complexity") else 5

        # Output format
        output_fmt = "markdown"
        if hasattr(strategy, "output_format_specification"):
            output_fmt = strategy.output_format_specification.value if hasattr(strategy.output_format_specification, "value") else str(strategy.output_format_specification)

        # BUG 6 FIX: Extract token budget from strategy and pass to composer
        token_budget = 500
        if hasattr(strategy, "estimated_tokens") and strategy.estimated_tokens:
            token_budget = strategy.estimated_tokens

        # BUG 2 FIX: Anti-hallucination system prompt
        system_prompt = (
            "You are a world-class prompt engineer. "
            "Your job is to craft a single, excellent prompt that another LLM will receive. "
            "The prompt you write should be ready to use immediately -- clear, well-structured, "
            "and incorporating the specified techniques naturally. "
            "Return ONLY the prompt text itself. No explanation, no meta-commentary.\n\n"
            "CRITICAL ANTI-HALLUCINATION RULES:\n"
            "1. ONLY use information that is EXPLICITLY provided in the user's request above.\n"
            "2. Do NOT invent, assume, or fabricate ANY specific details that are not in the user's input.\n"
            "3. Do NOT add specific names, numbers, technologies, salaries, company names, "
            "or any other concrete details that the user did not mention.\n"
            "4. If the user's request is vague or lacks specifics, add a 'CLARIFICATION NEEDED' "
            "section listing what information would improve the prompt -- do NOT fill in guesses.\n"
            "5. The prompt you write is for ANOTHER LLM to use. It should instruct that LLM, "
            "not contain your own reasoning about the task."
        )

        user_prompt = (
            f"Craft a high-quality prompt based on this specification:\n\n"
            f"## ORIGINAL USER REQUEST (use ONLY this information)\n{request}\n\n"
            f"## Domain\n{domain}\n\n"
            f"## Difficulty\n{diff_level} (technical complexity: {tech_score}/10)\n\n"
            f"## Techniques to incorporate\n{tech_block}\n\n"
            f"## Constraints\n{constraint_block}\n\n"
            f"## Target output format\n{output_fmt}\n\n"
            f"## Reasoning framework\n{strategy.reasoning_framework if hasattr(strategy, 'reasoning_framework') else 'analytical'}\n\n"
            f"## Token budget\nAim for approximately {token_budget} tokens.\n\n"
            f"Write the complete prompt now. Use Markdown headers (#, ##) for structure. "
            f"Make it professional, specific, and ready to use. "
            f"Remember: do NOT invent any details not present in the original user request."
        )

        raw = self.llm.generate(user_prompt, system_prompt=system_prompt)
        return _extract_prompt(raw)

    def _compose_from_templates(self, request, strategy, intent, difficulty) -> str:
        """
        Fallback: assemble prompt from technique templates.
        This is the original string-concatenation approach, improved.
        """
        parts = []

        # 1. ROLE section
        domain = "an expert AI assistant"
        if intent and hasattr(intent, "domain_knowledge_required") and intent.domain_knowledge_required:
            domain = "a " + ", ".join(intent.domain_knowledge_required) + " expert"
        role_text = TECHNIQUE_TEMPLATES.get("role", "# ROLE\nYou are an expert AI assistant.")
        role_text = role_text.replace("{domain}", domain)
        parts.append(role_text)

        # 2. TASK section
        parts.append(f"\n# TASK\n{request}")

        # 3. Technique sections (in ordering order if specified)
        tech_ids_used = set()
        if hasattr(strategy, "technique_ordering") and strategy.technique_ordering:
            ordered_ids = strategy.technique_ordering
        else:
            ordered_ids = [
                t.id if hasattr(t, "id") else t.get("id", "")
                for t in (strategy.selected_techniques if hasattr(strategy, "selected_techniques") else [])
            ]

        for tid in ordered_ids:
            if tid in TECHNIQUE_TEMPLATES and tid not in tech_ids_used:
                # Skip role (already added) and struct (handled separately)
                if tid in ("role", "audience", "style", "length", "constraints", "negative"):
                    continue
                parts.append(f"\n{TECHNIQUE_TEMPLATES[tid]}")
                tech_ids_used.add(tid)

        # 4. CONSTRAINTS section
        if difficulty and hasattr(difficulty, "risk_factors") and difficulty.risk_factors:
            parts.append(f"\n# CONSTRAINTS\n" + "\n".join(f"- Avoid: {r}" for r in difficulty.risk_factors))
        if intent and hasattr(intent, "constraints_identified") and intent.constraints_identified:
            for c in intent.constraints_identified:
                parts.append(f"- {c}")

        # 5. OUTPUT FORMAT section
        fmt = None
        if hasattr(strategy, "output_format_specification"):
            fmt = strategy.output_format_specification
        if fmt and (hasattr(fmt, "value") and fmt.value == "json") or fmt == "JSON":
            parts.append("\n# OUTPUT FORMAT\nReturn valid JSON only.")
        else:
            parts.append("\n# OUTPUT FORMAT\nProvide a clear, well-structured response.")

        return "\n".join(parts)

    def compose_simple(self, request_text: str, technique_ids: list[str] | None = None) -> str:
        """Quick composition without full pipeline context (for tests / CLI)."""
        parts = ["# ROLE\nYou are an expert AI assistant.\n", f"# TASK\n{request_text}\n"]
        if technique_ids:
            for tid in technique_ids:
                template = TECHNIQUE_TEMPLATES.get(tid)
                if template:
                    parts.append(template)
        return "\n".join(parts)

    def get_stage_info(self) -> dict:
        return {"name": "Prompt Composer", "stage": 6}