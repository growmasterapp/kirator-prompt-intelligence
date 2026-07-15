"""
Kirator Plugin Loader — auto-discovery, validation, lifecycle management.

Discovers plugins from:
  1. Built-in plugins/ directory (shipped with Kirator)
  2. User plugins/ directory (user-contributed, in project root)

Supports:
  - Auto-discovery via directory scanning
  - Interface validation (inherits KiratorPlugin, implements activate/deactivate)
  - Dependency resolution (plugins can declare dependencies on other plugins)
  - Hot-reload in development mode
  - Lazy loading
"""

import importlib
import importlib.util
import logging
import os
import sys
import time
from typing import Optional

from src.plugins.base import KiratorPlugin, PluginType, PluginState

logger = logging.getLogger(__name__)

# The 6 plugin subdirectories
PLUGIN_TYPES = ["analyzers", "techniques", "critics", "renderers", "models", "personas"]


class PluginLoader:
    """
    Discovers, validates, loads, and manages Kirator plugins.

    Usage:
        loader = PluginLoader(project_root="C:/KIRATOR_PROMPT_INTELLIGENCE")
        loader.discover()
        loader.load_all()
        plugins = loader.get_active_plugins(PluginType.TECHNIQUE)
    """

    def __init__(
        self,
        project_root: str = ".",
        builtin_dir: Optional[str] = None,
        user_dir: Optional[str] = None,
        hot_reload: bool = False,
    ):
        self.project_root = os.path.abspath(project_root)
        self.builtin_dir = builtin_dir or os.path.join(self.project_root, "src", "plugins")
        self.user_dir = user_dir or os.path.join(self.project_root, "plugins")
        self.hot_reload = hot_reload

        self._plugins: dict[str, KiratorPlugin] = {}  # plugin_id -> instance
        self._load_times: dict[str, float] = {}  # for hot-reload detection

    # ------------------------------------------------------------------
    # DISCOVERY
    # ------------------------------------------------------------------

    def discover(self) -> int:
        """
        Scan plugin directories for Python modules.
        Returns the number of plugins discovered.
        """
        found = 0
        search_dirs = []

        # Search both builtin and user directories
        if os.path.isdir(self.builtin_dir):
            for plugin_type in PLUGIN_TYPES:
                type_dir = os.path.join(self.builtin_dir, plugin_type)
                if os.path.isdir(type_dir):
                    search_dirs.append(type_dir)

        if os.path.isdir(self.user_dir):
            for plugin_type in PLUGIN_TYPES:
                type_dir = os.path.join(self.user_dir, plugin_type)
                if os.path.isdir(type_dir):
                    search_dirs.append(type_dir)

        for search_dir in search_dirs:
            for filename in os.listdir(search_dir):
                if filename.endswith(".py") and not filename.startswith("_"):
                    filepath = os.path.join(search_dir, filename)
                    try:
                        self._load_module(filepath)
                        found += 1
                    except Exception as e:
                        logger.warning(f"Failed to load plugin module {filepath}: {e}")

        logger.info(f"Plugin discovery complete: {found} modules scanned, {len(self._plugins)} plugins registered")
        return len(self._plugins)

    def _load_module(self, filepath: str) -> None:
        """Load a single Python module and extract KiratorPlugin subclasses."""
        module_name = os.path.splitext(os.path.basename(filepath))[0]

        # Avoid re-importing
        if module_name in sys.modules:
            # Hot-reload: if file changed, reload
            if self.hot_reload:
                mod = sys.modules[module_name]
                if hasattr(mod, "__file__") and mod.__file__:
                    file_mtime = os.path.getmtime(mod.__file__)
                    if self._load_times.get(module_name, 0) < file_mtime:
                        logger.info(f"Hot-reloading plugin: {module_name}")
                        importlib.reload(mod)

            # Extract plugins from cached module
            self._extract_plugins(sys.modules[module_name])
            return

        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return

        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            logger.error(f"Error executing plugin module {filepath}: {e}")
            return

        self._load_times[module_name] = os.path.getmtime(filepath)
        self._extract_plugins(mod)

    def _extract_plugins(self, module) -> None:
        """Find and register KiratorPlugin subclasses in a module."""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, KiratorPlugin)
                and attr is not KiratorPlugin
                and hasattr(attr, "PLUGIN_ID")
            ):
                plugin_id = attr.PLUGIN_ID
                if plugin_id not in self._plugins:
                    try:
                        instance = attr()
                        instance._state = PluginState.DISCOVERED
                        self._plugins[plugin_id] = instance
                        logger.debug(f"Discovered plugin: {plugin_id} ({attr.PLUGIN_TYPE.value})")
                    except Exception as e:
                        logger.warning(f"Failed to instantiate plugin {plugin_id}: {e}")

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def validate_all(self) -> tuple[int, int]:
        """
        Validate all discovered plugins.
        Returns (passed, failed) counts.
        """
        passed = 0
        failed = 0
        for pid, plugin in list(self._plugins.items()):
            if self._validate_plugin(plugin):
                plugin._state = PluginState.VALIDATED
                passed += 1
            else:
                plugin._state = PluginState.ERROR
                failed += 1
        logger.info(f"Plugin validation: {passed} passed, {failed} failed")
        return passed, failed

    def _validate_plugin(self, plugin: KiratorPlugin) -> bool:
        """Validate a single plugin's interface."""
        # Must have required class attributes
        if not hasattr(plugin, "PLUGIN_ID") or not plugin.PLUGIN_ID:
            plugin._error = "Missing PLUGIN_ID"
            return False
        if not hasattr(plugin, "PLUGIN_TYPE"):
            plugin._error = "Missing PLUGIN_TYPE"
            return False

        # Must implement abstract methods
        if not callable(getattr(plugin, "activate", None)):
            plugin._error = "Missing activate() method"
            return False
        if not callable(getattr(plugin, "deactivate", None)):
            plugin._error = "Missing deactivate() method"
            return False

        # Check dependencies exist
        for dep_id in plugin.PLUGIN_DEPENDENCIES:
            if dep_id not in self._plugins:
                plugin._error = f"Missing dependency: {dep_id}"
                return False

        return True

    # ------------------------------------------------------------------
    # LOADING & ACTIVATION
    # ------------------------------------------------------------------

    def load_all(self) -> int:
        """Validate and activate all plugins. Returns count activated."""
        self.validate_all()
        activated = 0
        for pid, plugin in self._plugins.items():
            if plugin._state == PluginState.VALIDATED:
                try:
                    plugin.activate()
                    plugin._state = PluginState.ACTIVE
                    activated += 1
                    logger.info(f"Activated plugin: {pid}")
                except Exception as e:
                    plugin._state = PluginState.ERROR
                    plugin._error = str(e)
                    logger.error(f"Failed to activate plugin {pid}: {e}")
        logger.info(f"Plugin loading complete: {activated} active")
        return activated

    def deactivate_plugin(self, plugin_id: str) -> bool:
        """Deactivate a specific plugin by ID."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        try:
            plugin.deactivate()
            plugin._state = PluginState.DEACTIVATED
            return True
        except Exception as e:
            plugin._error = str(e)
            return False

    def remove_plugin(self, plugin_id: str) -> bool:
        """Deactivate and remove a plugin from the registry."""
        if self.deactivate_plugin(plugin_id):
            self._plugins.pop(plugin_id, None)
            return True
        return False

    # ------------------------------------------------------------------
    # QUERIES
    # ------------------------------------------------------------------

    def get_plugin(self, plugin_id: str) -> Optional[KiratorPlugin]:
        return self._plugins.get(plugin_id)

    def get_active_plugins(self, plugin_type: PluginType | None = None) -> list[KiratorPlugin]:
        """Return all active plugins, optionally filtered by type."""
        plugins = [
            p for p in self._plugins.values()
            if p._state == PluginState.ACTIVE
        ]
        if plugin_type:
            plugins = [p for p in plugins if p.PLUGIN_TYPE == plugin_type]
        return plugins

    def get_all_plugins(self) -> dict[str, KiratorPlugin]:
        return dict(self._plugins)

    def get_plugin_count(self) -> dict[str, int]:
        """Return count by state."""
        counts = {}
        for p in self._plugins.values():
            state = p._state.value
            counts[state] = counts.get(state, 0) + 1
        return counts

    def get_summary(self) -> list[dict]:
        """Return info dict for all plugins."""
        return [p.get_info() for p in self._plugins.values()]

    # ------------------------------------------------------------------
    # HOT RELOAD
    # ------------------------------------------------------------------

    def check_hot_reload(self) -> int:
        """Check for changed plugin files and reload. Returns count reloaded."""
        if not self.hot_reload:
            return 0
        reloaded = 0

        # Deactivate all active plugins first
        for pid in list(self._plugins.keys()):
            self.deactivate_plugin(pid)

        # Clear and rediscover
        self._plugins.clear()
        self._load_times.clear()
        reloaded = self.discover()
        self.load_all()

        return reloaded