import ollama

from src.core.config import get_settings


class EmbeddingClient:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        settings = get_settings()
        self.model = model or settings.ollama.embedding_model
        self.client = ollama.Client(host=base_url or settings.ollama.base_url)

    def embed(self, text):
        r = self.client.embeddings(model=self.model, prompt=text)
        return r["embedding"]
