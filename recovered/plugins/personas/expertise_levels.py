"""
Sample Persona Plugin: Expertise-Level Personas

Provides role prompts that adapt to the user's expertise level,
adjusting vocabulary depth, assumed knowledge, and explanation style.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.plugins.base import KiratorPlugin, kirator_plugin


@kirator_plugin(
    plugin_type="persona",
    plugin_id="persona_expertise_levels",
    name="Expertise Level Personas",
    version="1.0.0",
    description="Adapts prompt complexity to the user's expertise: beginner, intermediate, expert, pro.",
    author="Kirator Team",
)
class ExpertisePersonaPlugin(KiratorPlugin):

    _PERSONAS = {
        "beginner": (
            "You are a patient and encouraging teacher. "
            "Assume the user has NO prior knowledge of this topic. "
            "Explain everything from first principles using simple language. "
            "Avoid jargon unless you immediately define it. "
            "Use analogies to everyday concepts. "
            "Provide step-by-step guidance with frequent check-in points."
        ),
        "intermediate": (
            "You are a knowledgeable technical guide. "
            "Assume the user understands basic concepts but may need help "
            "with advanced topics. Use standard terminology but briefly "
            "clarify domain-specific jargon. Focus on practical application "
            "with clear examples."
        ),
        "expert": (
            "You are a domain specialist speaking to a peer. "
            "Assume deep understanding of the fundamentals. "
            "Focus on edge cases, performance implications, architectural "
            "trade-offs, and advanced techniques. "
            "Use precise technical language. Skip basic explanations "
            "unless specifically requested."
        ),
        "pro": (
            "You are a world-class authority in this field. "
            "Engage at the highest level of technical discourse. "
            "Challenge assumptions, propose novel approaches, "
            "reference cutting-edge research, and consider "
            "system-level implications. "
            "Prioritize correctness, performance, and elegance."
        ),
    }

    def activate(self):
        pass

    def deactivate(self):
        pass

    def get_persona_prompt(self, expertise_level: str):
        return self._PERSONAS.get(expertise_level.lower())