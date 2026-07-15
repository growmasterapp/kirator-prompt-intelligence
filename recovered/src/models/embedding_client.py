import ollama

class EmbeddingClient:
    def __init__(self):
        self.client = ollama.Client()
    
    def embed(self, text):
        r = self.client.embeddings(model="bge-m3", prompt=text)
        return r["embedding"]
