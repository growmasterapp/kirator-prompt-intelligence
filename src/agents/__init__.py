"""
Reusable agent façades for the Kirator AI workspace.

Today the primary agent is PromptArchitect (the 9-stage pipeline).
Additional agents (Researcher, Critic, ReverseEngineer) can plug into
the same service contracts without growing the Flask layer.
"""

from src.agents.prompt_architect import PromptArchitectAgent

__all__ = ["PromptArchitectAgent"]
