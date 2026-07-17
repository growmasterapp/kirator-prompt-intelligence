"""
Central configuration loader for Kirator Prompt Intelligence.

Loads config/settings.yaml with sensible defaults. All modules should
prefer get_settings() over hardcoded URLs, ports, and model names.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    """Resolve project root for both source and frozen (PyInstaller) runs."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # src/core/config.py → parents[2] = project root
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str = "http://localhost:11434"
    reasoning_model: str = "deepseek-r1:8b"
    composition_model: str = "llama3.1:8b"
    embedding_model: str = "bge-m3"
    timeout_seconds: int = 120
    max_retries: int = 2


@dataclass(frozen=True)
class ServerSettings:
    host: str = "127.0.0.1"
    port: int = 5000
    browser_delay_seconds: float = 3.0


@dataclass(frozen=True)
class PipelineSettings:
    quality_threshold: int = 85
    max_optimize_iterations: int = 2
    history_max: int = 50
    poll_dedupe_seconds: float = 5.0


@dataclass(frozen=True)
class Settings:
    project_name: str = "Kirator Prompt Intelligence"
    project_version: str = "1.1.0"
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)
    data_dir: Path = field(default_factory=lambda: project_root() / "src" / "data")
    user_data_dir: Path = field(
        default_factory=lambda: Path.home() / ".kirator" / "prompt_intelligence"
    )


def _deep_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    return loaded if isinstance(loaded, dict) else {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache application settings."""
    root = project_root()
    raw = _load_yaml(root / "config" / "settings.yaml")

    ollama = OllamaSettings(
        base_url=str(_deep_get(raw, "ollama", "base_url", default=OllamaSettings.base_url)),
        reasoning_model=str(
            _deep_get(raw, "ollama", "reasoning_model", default=OllamaSettings.reasoning_model)
        ),
        composition_model=str(
            _deep_get(
                raw, "ollama", "composition_model", default=OllamaSettings.composition_model
            )
        ),
        embedding_model=str(
            _deep_get(raw, "ollama", "embedding_model", default=OllamaSettings.embedding_model)
        ),
        timeout_seconds=int(
            _deep_get(raw, "ollama", "timeout_seconds", default=OllamaSettings.timeout_seconds)
        ),
        max_retries=int(
            _deep_get(raw, "ollama", "max_retries", default=OllamaSettings.max_retries)
        ),
    )

    server = ServerSettings(
        host=str(_deep_get(raw, "server", "host", default=ServerSettings.host)),
        port=int(_deep_get(raw, "server", "port", default=ServerSettings.port)),
        browser_delay_seconds=float(
            _deep_get(
                raw,
                "server",
                "browser_delay_seconds",
                default=ServerSettings.browser_delay_seconds,
            )
        ),
    )

    pipeline = PipelineSettings(
        quality_threshold=int(
            _deep_get(
                raw, "pipeline", "quality_threshold", default=PipelineSettings.quality_threshold
            )
        ),
        max_optimize_iterations=int(
            _deep_get(
                raw,
                "pipeline",
                "max_optimize_iterations",
                default=PipelineSettings.max_optimize_iterations,
            )
        ),
        history_max=int(
            _deep_get(raw, "pipeline", "history_max", default=PipelineSettings.history_max)
        ),
        poll_dedupe_seconds=float(
            _deep_get(
                raw,
                "pipeline",
                "poll_dedupe_seconds",
                default=PipelineSettings.poll_dedupe_seconds,
            )
        ),
    )

    data_dir = Path(
        _deep_get(raw, "paths", "data_dir", default=str(root / "src" / "data"))
    )
    if not data_dir.is_absolute():
        data_dir = root / data_dir

    user_data = Path(
        os.environ.get(
            "KIRATOR_USER_DATA",
            _deep_get(
                raw,
                "paths",
                "user_data_dir",
                default=str(Path.home() / ".kirator" / "prompt_intelligence"),
            ),
        )
    )

    return Settings(
        project_name=str(
            _deep_get(raw, "project", "name", default="Kirator Prompt Intelligence")
        ),
        project_version=str(_deep_get(raw, "project", "version", default="1.1.0")),
        ollama=ollama,
        server=server,
        pipeline=pipeline,
        data_dir=data_dir,
        user_data_dir=user_data,
    )


def reload_settings() -> Settings:
    """Clear cache and reload (useful in tests)."""
    get_settings.cache_clear()
    return get_settings()
