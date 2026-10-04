import hashlib
import logging
import threading
import time

import ollama

from src.core.config import get_settings
from src.core.exceptions import PipelineCancelled
from src.models.cancellable import run_interruptible

logger = logging.getLogger(__name__)


class OllamaClient:
    """Wrapper around the Ollama REST client with caching, retry, and timeout support."""

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
    ):
        settings = get_settings().ollama
        self.base_url = base_url or settings.base_url
        self.default_model = default_model or settings.reasoning_model
        self.timeout_seconds = timeout_seconds or settings.timeout_seconds
        self._client = None
        self._lock = threading.Lock()

        self._cache: dict[tuple[str, str], str] = {}
        self._cache_enabled = True
        self.max_retries = max_retries if max_retries is not None else settings.max_retries
        self.retry_delay = 1.0
        self._cancel_event: threading.Event | None = None
        self._aborted = False

        logger.info("OllamaClient init model=%s host=%s", self.default_model, self.base_url)
        try:
            self.client = ollama.Client(host=self.base_url, timeout=self.timeout_seconds)
        except Exception as e:
            raise Exception(f"Failed to connect to Ollama: {e}") from e

    @property
    def client(self) -> ollama.Client:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = ollama.Client(
                        host=self.base_url, timeout=self.timeout_seconds
                    )
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    def _cache_key(self, prompt: str, system_prompt: str | None) -> tuple[str, str]:
        raw = (system_prompt or "") + "|||" + prompt
        h = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
        return (self.default_model, h)

    def enable_cache(self, enabled: bool = True):
        self._cache_enabled = enabled

    def clear_cache(self):
        self._cache.clear()

    def bind_cancel(self, cancel_event: threading.Event | None) -> None:
        """Watch this event so a running generate() can stop early."""
        self._cancel_event = cancel_event
        self._aborted = False

    def abort(self) -> None:
        """Close the HTTP client so a stuck model call unblocks."""
        self._aborted = True
        client = self._client
        if client is None:
            return
        inner = getattr(client, "_client", None)
        if inner is None:
            return
        try:
            inner.close()
        except Exception:
            logger.debug("Could not close Ollama HTTP client", exc_info=True)

    def _cancelled(self) -> bool:
        if self._aborted:
            return True
        event = self._cancel_event
        return event is not None and event.is_set()

    def _sleep_or_cancel(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self._cancelled():
                raise PipelineCancelled("Cancelled during retry wait")
            time.sleep(0.1)

    def generate(self, prompt, system_prompt=None, use_cache=True):
        if self._cancelled():
            raise PipelineCancelled("Cancelled before model call")

        if self._cache_enabled and use_cache:
            key = self._cache_key(prompt, system_prompt)
            if key in self._cache:
                logger.debug("Cache hit for %s", self.default_model)
                return self._cache[key]

        logger.info("Calling %s…", self.default_model)
        start = time.time()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(1, self.max_retries + 2):
            if self._cancelled():
                raise PipelineCancelled("Cancelled before model call")
            try:
                result = self._chat(messages)
                elapsed = time.time() - start
                logger.info("Response from %s in %.1fs", self.default_model, elapsed)

                if self._cache_enabled and use_cache:
                    key = self._cache_key(prompt, system_prompt)
                    self._cache[key] = result
                return result
            except PipelineCancelled:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "Attempt %s/%s failed for %s: %s",
                    attempt,
                    self.max_retries + 1,
                    self.default_model,
                    e,
                )
                if attempt <= self.max_retries:
                    self._sleep_or_cancel(self.retry_delay)

        if self._cancelled():
            raise PipelineCancelled("Cancelled during model call")
        logger.error("All attempts failed for %s", self.default_model)
        raise last_error

    def _chat(self, messages) -> str:
        """One model call that Cancel can interrupt."""

        def _call() -> str:
            response = self.client.chat(
                model=self.default_model,
                messages=messages,
            )
            return response["message"]["content"]

        return run_interruptible(_call, self._cancel_event, self.abort)
