"""
Sample Technique Plugin: Prompt Chaining

Adds a 'chain' technique that instructs the model to break output
into sequential steps, producing intermediate results before the final answer.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.plugins.base import KiratorPlugin, PluginType, kirator_plugin


@kirator_plugin(
    plugin_type="technique",
    plugin_id="tech_prompt_chaining",
    name="Prompt Chaining",
    version="1.0.0",
    description="Breaks complex tasks into a chain of sequential prompts, each building on the last.",
    author="Kirator Team",
)
class PromptChainingPlugin(KiratorPlugin):

    def __init__(self):
        super().__init__()
        self._chaining_techniques = []

    def activate(self):
        self._chaining_techniques = [
            {
                "id": "chaining",
                "name": "Prompt Chaining",
                "category": "decomposition",
                "description": "Breaks the task into a chain of sequential steps. Each step's output feeds into the next prompt.",
                "effectiveness_score": 0.87,
                "complexity_overhead": 3,
                "tags": ["chain", "sequential", "step by step", "multi-step", "pipeline", "workflow", "series", "then"],
            },
            {
                "id": "branching",
                "name": "Branching Chaining",
                "category": "decomposition",
                "description": "Creates parallel prompt chains that explore different approaches, then merges results.",
                "effectiveness_score": 0.82,
                "complexity_overhead": 4,
                "tags": ["branch", "parallel", "explore", "multiple paths", "compare", "merge", "fork"],
            },
        ]

    def deactivate(self):
        self._chaining_techniques = []

    def get_techniques(self):
        return self._chaining_techniques