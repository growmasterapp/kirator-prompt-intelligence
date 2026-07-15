import ollama
import logging
import time
import hashlib
import threading

logger = logging.getLogger(__name__)

# Default timeout for Ollama calls (seconds)
DEFAULT_TIMEOUT = 120


class OllamaClient:
    """Wrapper around the Ollama REST client with caching, retry, and timeout support."""

    def __init__(self, base_url="http://localhost:11434", default_model="deepseek-r1:8b"):
        self.base_url = base_url
        self.default_model = default_model
        self._client = None
        self._lock = threading.Lock()

        # Response cache: key = (model, prompt_hash) -> response string
        self._cache: dict[tuple[str, str], str] = {}
        self._cache_enabled = True

        # Retry configuration
        self.max_retries = 2
        self.retry_delay = 1.0  # seconds between retries

        print(f'[OllamaClient] Initializing with model: {default_model}')
        try:
            self.client = ollama.Client(host=base_url, timeout=DEFAULT_TIMEOUT)
            print(f'[OllamaClient] Connected to Ollama at {base_url}')
        except Exception as e:
            raise Exception(f'Failed to connect to Ollama: {e}')

    @property
    def client(self) -> ollama.Client:
        """Lazy client accessor (thread-safe)."""
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = ollama.Client(host=self.base_url, timeout=DEFAULT_TIMEOUT)
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    def _cache_key(self, prompt: str, system_prompt: str | None) -> tuple[str, str]:
        """Generate a deterministic cache key from model + full prompt content."""
        raw = (system_prompt or "") + "|||" + prompt
        h = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
        return (self.default_model, h)

    def enable_cache(self, enabled: bool = True):
        """Enable or disable response caching."""
        self._cache_enabled = enabled

    def clear_cache(self):
        """Clear all cached responses."""
        self._cache.clear()

    def generate(self, prompt, system_prompt=None, use_cache=True):
        # Check cache first
        if self._cache_enabled and use_cache:
            key = self._cache_key(prompt, system_prompt)
            if key in self._cache:
                logger.debug(f"[OllamaClient] Cache hit for {self.default_model}")
                return self._cache[key]

        print(f'[OllamaClient] Calling {self.default_model}...')
        print(f'[OllamaClient] Prompt: {prompt[:80]}...')

        start = time.time()

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        last_error = None
        for attempt in range(1, self.max_retries + 2):  # 1 initial + max_retries retries
            try:
                response = self.client.chat(
                    model=self.default_model,
                    messages=messages,
                )

                elapsed = time.time() - start
                result = response['message']['content']

                print(f'[OllamaClient] Response received in {elapsed:.1f}s')
                print(f'[OllamaClient] Response preview: {result[:100]}...')

                # Cache the result
                if self._cache_enabled and use_cache:
                    key = self._cache_key(prompt, system_prompt)
                    self._cache[key] = result

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    f'[OllamaClient] Attempt {attempt}/{self.max_retries + 1} '
                    f'failed for {self.default_model}: {e}'
                )
                if attempt <= self.max_retries:
                    time.sleep(self.retry_delay)

        # All retries exhausted
        logger.error(f'[OllamaClient] All {self.max_retries + 1} attempts failed for {self.default_model}')
        raise last_error