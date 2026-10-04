"""
Kirator Plugin System — Base Classes

Every plugin MUST inherit from KiratorPlugin and implement:
  - plugin_type: str (one of the 6 supported types)
  - plugin_id: str (unique identifier)
  - plugin_version: str (semver)

Plugin lifecycle:
  1. DISCOVER — found in plugins/ directory
  2. VALIDATE — interface checks pass
  3. LOAD    — Python module imported
  4. ACTIVATE — plugin.activate() called
  5. DEACTIVATE — plugin.deactivate() called (on unload)
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PluginType(str, Enum):
    """The 6 supported plugin types."""
    ANALYZER = "analyzer"
    TECHNIQUE = "technique"
    CRITIC = "critic"
    RENDERER = "renderer"
    MODEL_ADAPTER = "model_adapter"
    PERSONA = "persona"


class PluginState(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DEACTIVATED = "deactivated"


class KiratorPlugin(ABC):
    """
    Abstract base class for all Kirator plugins.

    Every plugin must define these class attributes:
      - PLUGIN_TYPE: PluginType
      - PLUGIN_ID: str
      - PLUGIN_VERSION: str
      - PLUGIN_NAME: str (human-readable)

    And implement these methods:
      - activate() -> None
      - deactivate() -> None
      - get_info() -> dict
    """

    PLUGIN_TYPE: PluginType
    PLUGIN_ID: str
    PLUGIN_VERSION: str = "1.0.0"
    PLUGIN_NAME: str = "Unnamed Plugin"
    PLUGIN_DESCRIPTION: str = ""
    PLUGIN_AUTHOR: str = ""
    PLUGIN_DEPENDENCIES: list[str] = []  # List of plugin IDs this depends on
    PLUGIN_MIN_KIRATOR_VERSION: str = "2.0.0"

    # Runtime state (set by loader)
    _state: PluginState = PluginState.DISCOVERED
    _error: Optional[str] = None

    @abstractmethod
    def activate(self) -> None:
        """Called when the plugin is activated. Set up resources here."""
        ...

    @abstractmethod
    def deactivate(self) -> None:
        """Called when the plugin is deactivated. Clean up resources here."""
        ...

    def get_info(self) -> dict:
        """Return plugin metadata as a dict."""
        return {
            "id": self.PLUGIN_ID,
            "type": self.PLUGIN_TYPE.value,
            "name": self.PLUGIN_NAME,
            "version": self.PLUGIN_VERSION,
            "description": self.PLUGIN_DESCRIPTION,
            "author": self.PLUGIN_AUTHOR,
            "dependencies": self.PLUGIN_DEPENDENCIES,
            "state": self._state.value,
            "error": self._error,
        }

    # ------------------------------------------------------------------
    # TYPE-SPECIFIC INTERFACE METHODS
    # Each plugin type overrides the methods relevant to it.
    # ------------------------------------------------------------------

    # --- Analyzer plugins ---
    def analyze_intent(self, request: str, context: dict) -> Optional[dict]:
        """Custom intent analysis. Return dict or None to defer to default."""
        return None

    def analyze_difficulty(self, request: str, context: dict, intent: dict) -> Optional[dict]:
        """Custom difficulty analysis. Return dict or None to defer."""
        return None

    # --- Technique plugins ---
    def get_techniques(self) -> list[dict]:
        """Return list of technique dicts this plugin provides."""
        return []

    # --- Critic plugins ---
    def evaluate(self, prompt_text: str, target_model: str) -> Optional[dict]:
        """Custom quality evaluation. Return score dict or None to defer."""
        return None

    # --- Renderer plugins ---
    def render(self, prompt: str, report: dict, strategy: dict, stats: dict) -> Optional[str]:
        """Custom rendering. Return rendered string or None to defer."""
        return None

    # --- Model adapter plugins ---
    def get_client(self, model_name: str):
        """Return a model client for the given model name."""
        return None

    # --- Persona plugins ---
    def get_persona_prompt(self, expertise_level: str) -> Optional[str]:
        """Return a persona system prompt for the given expertise level."""
        return None


# ================================================================
# CONVENIENCE DECORATOR FOR PLUGIN REGISTRATION
# ================================================================

def kirator_plugin(
    plugin_type: str,
    plugin_id: str,
    name: str = "",
    version: str = "1.0.0",
    description: str = "",
    author: str = "",
):
    """
    Decorator to register a class as a Kirator plugin.

    Usage:
        @kirator_plugin(
            plugin_type="analyzer",
            plugin_id="my_custom_analyzer",
            name="My Custom Analyzer",
            version="1.0.0",
        )
        class MyAnalyzer(KiratorPlugin):
            ...
    """
    def decorator(cls):
        cls.PLUGIN_TYPE = PluginType(plugin_type)
        cls.PLUGIN_ID = plugin_id
        cls.PLUGIN_NAME = name or plugin_id
        cls.PLUGIN_VERSION = version
        cls.PLUGIN_DESCRIPTION = description
        cls.PLUGIN_AUTHOR = author
        return cls

    return decorator