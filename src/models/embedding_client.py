import threading

import ollama

from src.core.config import get_settings
from src.core.exceptions import PipelineCancelled
from src.models.cancellable import run_interruptible


class EmbeddingClient:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        settings = get_settings()
        self.model = model or settings.ollama.embedding_model
        self.client = ollama.Client(host=base_url or settings.ollama.base_url)
        self._cancel_event: threading.Event | None = None
        self._aborted = False

    def bind_cancel(self, cancel_event: threading.Event | None) -> None:
        self._cancel_event = cancel_event
        self._aborted = False

    def abort(self) -> None:
        """Close the HTTP client so a stuck embedding call unblocks."""
        self._aborted = True
        inner = getattr(self.client, "_client", None)
        if inner is None:
            return
        try:
            inner.close()
        except Exception:
            pass

    def embed(self, text):
        if self._aborted or (self._cancel_event is not None and self._cancel_event.is_set()):
            raise PipelineCancelled("Cancelled before embedding")

        def _call():
            response = self.client.embeddings(model=self.model, prompt=text)
            return response["embedding"]

        return run_interruptible(_call, self._cancel_event, self.abort)
