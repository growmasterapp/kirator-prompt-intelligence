import logging
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models.ollama_client import OllamaClient
from src.stages.stage7_prompt_critic.critic import PromptCritic
from src.core.models import PromptQualityScore

logger = logging.getLogger(__name__)


def _strip_thinking_artifacts(text: str) -> str:
    """Strip DeepSeek thinking blocks and other LLM artifacts from optimized prompt."""
    text = re.sub(r"__(?:START|END) THINKING__", "", text, flags=re.DOTALL)
    text = re.sub(r"__[A-Z\s]+__", "", text)
    text = re.sub(r"^(?:here is (?:the )?(?:an? )?(?:improved|optimized) (?:prompt|version)[:\s]*,?\s*)",
                  "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n*(?:note:|explanation:|this prompt|let me know if).*$",
                  "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


class PromptOptimizer:
    """Self-critique loop: evaluate -> refine -> re-evaluate until quality threshold.

    v2: BUG 4 FIX -- Added early exit when score >= 80 (skip S8 entirely),
    early exit when iteration doesn't improve by >= 3 points, and thinking
    artifact stripping from optimized prompts.
    """

    # Minimum improvement required to continue optimizing
    MIN_IMPROVEMENT_THRESHOLD = 3

    # Skip optimization entirely if S7 score is at or above this
    SKIP_OPTIMIZATION_THRESHOLD = 80

    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client
        self.critic = PromptCritic(llm_client)

    def optimize(
        self,
        prompt_text: str,
        target_model: str = "generic",
        max_iterations: int = 3,
        quality_threshold: int = 85,
    ) -> dict:
        """
        Iteratively refine a prompt using critic feedback.

        Returns dict with keys:
            optimized_prompt, final_score, iterations_used,
            converged, history, quality_report
        """
        current_prompt = prompt_text
        history: list[dict] = []

        system_prompt = (
            "You are an expert prompt engineer. "
            "Improve the given prompt based on the critique. "
            "Keep the same core meaning and goal. "
            "Return ONLY the improved prompt text -- no explanation, no markdown wrapper."
        )

        for i in range(max_iterations):
            score: PromptQualityScore = self.critic.evaluate(current_prompt, target_model)
            history.append({
                "iteration": i + 1,
                "score": score.overall_score,
                "prompt": current_prompt,
            })

            # Already above threshold -- done
            if score.overall_score >= quality_threshold:
                return self._build_result(current_prompt, score, history, i + 1, quality_threshold, converged=True)

            # BUG 4 FIX: Skip optimization if score is already good (>= 80)
            # The marginal gain isn't worth the ~15-20 seconds of LLM calls
            if i == 0 and score.overall_score >= self.SKIP_OPTIMIZATION_THRESHOLD:
                logger.info(
                    f"S8: Score {score.overall_score} >= {self.SKIP_OPTIMIZATION_THRESHOLD}, "
                    f"skipping optimization (would waste time for marginal gain)"
                )
                return self._build_result(current_prompt, score, history, i + 1, quality_threshold, converged=False)

            # Build refinement instruction from critic feedback
            if score.improvements:
                improvement_text = "\n".join("- " + imp for imp in score.improvements)
            else:
                improvement_text = "- Improve clarity and specificity\n- Add missing constraints"

            refine_prompt = (
                "Improve this prompt based on the following critique.\n"
                "Keep the same core meaning and goal but fix the identified weaknesses.\n\n"
                "CURRENT PROMPT:\n"
                + current_prompt
                + "\n\nWEAKNESSES TO FIX:\n"
                + improvement_text
                + "\n\nReturn ONLY the improved prompt text. No explanation, no markdown, just the prompt."
            )

            try:
                improved = self.llm.generate(refine_prompt, system_prompt=system_prompt)
                # Strip thinking artifacts from the improved prompt
                improved = _strip_thinking_artifacts(improved)

                if not improved or len(improved) < 50:
                    logger.warning(f"Optimization iteration {i + 1}: improved prompt too short or empty, stopping")
                    break

                # Re-evaluate to check if we actually improved
                new_score: PromptQualityScore = self.critic.evaluate(improved, target_model)
                improvement_delta = new_score.overall_score - score.overall_score

                # BUG 4 FIX: Early exit if no meaningful improvement
                if improvement_delta < self.MIN_IMPROVEMENT_THRESHOLD:
                    logger.info(
                        f"S8: Iteration {i + 1} only improved by {improvement_delta} pts "
                        f"(threshold: {self.MIN_IMPROVEMENT_THRESHOLD}), stopping early"
                    )
                    # Keep the original if the "improved" version is worse
                    if improvement_delta < 0:
                        logger.info("S8: Optimized version is WORSE, keeping original")
                    else:
                        current_prompt = improved
                    break

                # Meaningful improvement -- accept and continue
                current_prompt = improved
                logger.info(f"S8: Iteration {i + 1} improved by {improvement_delta} pts (now {new_score.overall_score}/100)")

            except Exception as e:
                logger.error(f"Optimization iteration {i + 1} failed: {e}")
                break

        # Final evaluation after loop exits
        final_score: PromptQualityScore = self.critic.evaluate(current_prompt, target_model)
        converged = final_score.overall_score >= quality_threshold
        return self._build_result(current_prompt, final_score, history, min(max_iterations, len(history)), quality_threshold, converged=converged)

    @staticmethod
    def _build_result(
        prompt: str,
        score: PromptQualityScore,
        history: list[dict],
        iterations: int,
        threshold: int,
        converged: bool,
    ) -> dict:
        return {
            "optimized_prompt": prompt,
            "final_score": score.overall_score,
            "iterations_used": iterations,
            "converged": converged,
            "history": history,
            "quality_report": score.to_dict(),
        }

    def get_stage_info(self) -> dict:
        return {"name": "Prompt Optimizer", "stage": 8}