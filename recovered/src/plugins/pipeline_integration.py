"""
Plugin-Pipeline Integration Layer

Wires active plugins into the 9-stage pipeline at the correct injection points:
  - analyzer plugins  → enrich S2 intent analysis results
  - technique plugins → merge additional techniques into S5 results  
  - critic plugins    → merge additional evaluation axes into S7 results
  - persona plugins   → inject persona prompts into S6 composition context
  - renderer plugins  → provide alternative rendering in S9
  - model_adapter plugins → provide alternative LLM clients
"""

import logging
from typing import Optional
from src.plugins.base import KiratorPlugin, PluginType
from src.plugins.loader import PluginLoader

logger = logging.getLogger(__name__)


class PluginAwarePipeline:
    """
    Wraps the plugin system and provides methods to inject plugin results
    into each pipeline stage.
    
    Usage in kirator.py:
        plugin_pipeline = PluginAwarePipeline(loader)
        
        # After S2 intent analysis:
        intent = plugin_pipeline.enrich_intent(request, intent, context)
        
        # After S5 technique search:
        techniques = plugin_pipeline.enrich_techniques(request, techniques)
        
        # After S7 critic evaluation:
        quality = plugin_pipeline.enrich_quality(prompt_text, quality_report, target_model)
        
        # During S6 composition (get persona prompt):
        persona_prompt = plugin_pipeline.get_persona_prompt(expertise_level)
        
        # In S9 rendering:
        rendered = plugin_pipeline.render_alternative(prompt, report, strategy, stats)
    """
    
    def __init__(self, loader: PluginLoader):
        self.loader = loader
        self._cache_analyzers = []
        self._cache_techniques = []
        self._cache_critics = []
        self._cache_renderers = []
        self._cache_personas = []
        self._cache_model_adapters = []
        self._build_caches()
    
    def _build_caches(self):
        """Cache active plugins by type for fast access."""
        self._cache_analyzers = self.loader.get_active_plugins(PluginType.ANALYZER)
        self._cache_techniques = self.loader.get_active_plugins(PluginType.TECHNIQUE)
        self._cache_critics = self.loader.get_active_plugins(PluginType.CRITIC)
        self._cache_renderers = self.loader.get_active_plugins(PluginType.RENDERER)
        self._cache_personas = self.loader.get_active_plugins(PluginType.PERSONA)
        self._cache_model_adapters = self.loader.get_active_plugins(PluginType.MODEL_ADAPTER)
        logger.info(
            f"Plugin pipeline caches built: "
            f"{len(self._cache_analyzers)} analyzers, "
            f"{len(self._cache_techniques)} techniques, "
            f"{len(self._cache_critics)} critics, "
            f"{len(self._cache_renderers)} renderers, "
            f"{len(self._cache_personas)} personas, "
            f"{len(self._cache_model_adapters)} model adapters"
        )
    
    def enrich_intent(self, request: str, intent, context: dict) -> dict:
        """
        Run all analyzer plugins and merge their results into the intent dict.
        
        Each analyzer's analyze_intent() returns a dict or None.
        Merge non-None results into the intent dict (as a dict if it's a Pydantic model).
        
        Returns the enriched intent dict.
        """
        intent_dict = {}
        if hasattr(intent, "model_dump"):
            intent_dict = intent.model_dump()
        elif hasattr(intent, "dict"):
            intent_dict = intent.dict()
        elif isinstance(intent, dict):
            intent_dict = dict(intent)
        
        for plugin in self._cache_analyzers:
            try:
                result = plugin.analyze_intent(request, context)
                if result and isinstance(result, dict):
                    intent_dict.update(result)
                    logger.debug(f"Analyzer plugin {plugin.PLUGIN_ID} enriched intent: {list(result.keys())}")
            except Exception as e:
                logger.warning(f"Analyzer plugin {plugin.PLUGIN_ID} failed: {e}")
        
        return intent_dict
    
    def enrich_techniques(self, request: str, techniques: list[dict]) -> list[dict]:
        """
        Merge additional techniques from technique plugins into the S5 results.
        
        Each technique plugin's get_techniques() returns a list of technique dicts.
        These are appended to the existing techniques list (avoiding duplicates by ID).
        
        Returns the merged techniques list.
        """
        existing_ids = {t.get("id") for t in techniques if isinstance(t, dict)}
        merged = list(techniques)
        
        for plugin in self._cache_techniques:
            try:
                plugin_techs = plugin.get_techniques()
                if plugin_techs:
                    for tech in plugin_techs:
                        if isinstance(tech, dict) and tech.get("id") not in existing_ids:
                            tech["_source"] = f"plugin:{plugin.PLUGIN_ID}"
                            merged.append(tech)
                            existing_ids.add(tech["id"])
                    logger.debug(f"Technique plugin {plugin.PLUGIN_ID} added {len(plugin_techs)} techniques")
            except Exception as e:
                logger.warning(f"Technique plugin {plugin.PLUGIN_ID} failed: {e}")
        
        return merged
    
    def enrich_quality(self, prompt_text: str, quality_report: dict, target_model: str = "generic") -> dict:
        """
        Run all critic plugins and merge their evaluation results into the quality report.
        
        Each critic's evaluate() returns a dict or None.
        Non-None results are merged into the quality_report dict.
        
        Returns the enriched quality report dict.
        """
        enriched = dict(quality_report) if quality_report else {}
        
        for plugin in self._cache_critics:
            try:
                result = plugin.evaluate(prompt_text, target_model)
                if result and isinstance(result, dict):
                    enriched[f"plugin_{plugin.PLUGIN_ID}"] = result
                    logger.debug(f"Critic plugin {plugin.PLUGIN_ID} added evaluation axes")
            except Exception as e:
                logger.warning(f"Critic plugin {plugin.PLUGIN_ID} failed: {e}")
        
        return enriched
    
    def get_persona_prompt(self, expertise_level: str) -> Optional[str]:
        """
        Get a persona system prompt from persona plugins.
        
        Returns the first non-None result from any persona plugin,
        or None if no persona matches.
        """
        for plugin in self._cache_personas:
            try:
                result = plugin.get_persona_prompt(expertise_level)
                if result:
                    logger.debug(f"Persona plugin {plugin.PLUGIN_ID} provided prompt for '{expertise_level}'")
                    return result
            except Exception as e:
                logger.warning(f"Persona plugin {plugin.PLUGIN_ID} failed: {e}")
        
        return None
    
    def render_alternative(self, prompt: str, report: dict, strategy: dict, stats: dict) -> Optional[str]:
        """
        Try all renderer plugins for an alternative rendering.
        
        Returns the first non-None result from any renderer plugin,
        or None to fall back to the default renderer.
        """
        for plugin in self._cache_renderers:
            try:
                result = plugin.render(prompt, report, strategy, stats)
                if result:
                    logger.debug(f"Renderer plugin {plugin.PLUGIN_ID} produced output")
                    return result
            except Exception as e:
                logger.warning(f"Renderer plugin {plugin.PLUGIN_ID} failed: {e}")
        
        return None
    
    def get_model_client(self, model_name: str):
        """
        Get a model client from model adapter plugins.
        
        Returns the first non-None client from any model adapter,
        or None to fall back to the default OllamaClient.
        """
        for plugin in self._cache_model_adapters:
            try:
                client = plugin.get_client(model_name)
                if client:
                    logger.debug(f"Model adapter {plugin.PLUGIN_ID} provided client for '{model_name}'")
                    return client
            except Exception as e:
                logger.warning(f"Model adapter plugin {plugin.PLUGIN_ID} failed: {e}")
        
        return None
    
    def get_plugin_summary(self) -> dict:
        """Return a summary of all active plugins and their injection points."""
        return {
            "analyzers": [p.PLUGIN_ID for p in self._cache_analyzers],
            "techniques": [p.PLUGIN_ID for p in self._cache_techniques],
            "critics": [p.PLUGIN_ID for p in self._cache_critics],
            "renderers": [p.PLUGIN_ID for p in self._cache_renderers],
            "personas": [p.PLUGIN_ID for p in self._cache_personas],
            "model_adapters": [p.PLUGIN_ID for p in self._cache_model_adapters],
        }