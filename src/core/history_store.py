"""Durable prompt-run history stored under the user data directory."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from src.core.config import get_settings
from src.core.logging_setup import get_logger

logger = get_logger(__name__)


class HistoryStore:
    def __init__(self, path: Path | None = None, max_entries: int | None = None):
        settings = get_settings()
        self.max_entries = max_entries or settings.pipeline.history_max
        self.path = path or (settings.user_data_dir / "history.json")
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to read history: %s", e)
            return []

    def _write(self, entries: list[dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def add(
        self,
        request_text: str,
        score: int,
        total_time: float,
        target_model: str = "generic",
        prompt_preview: str = "",
    ) -> dict[str, Any]:
        entry = {
            "request": request_text[:200],
            "score": score,
            "time": total_time,
            "model": target_model,
            "prompt_preview": prompt_preview[:160],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with self._lock:
            entries = self._read()
            entries.insert(0, entry)
            entries = entries[: self.max_entries]
            self._write(entries)
        return entry

    def clear(self) -> None:
        with self._lock:
            self._write([])
