import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.config import Settings

CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "chroma_data")

class KiratorVectorDB:
    def __init__(self, persist_dir=None):
        d = persist_dir or CHROMA_DIR
        os.makedirs(d, exist_ok=True)
        self.client = chromadb.PersistentClient(path=d)
        self.collection = self.client.get_or_create_collection(
            name="techniques",
            metadata={"description": "Prompting techniques library"}
        )

    def add_technique(self, tech_id, name, category, description, tags, effectiveness):
        self.collection.upsert(
            ids=[tech_id],
            documents=[description],
            metadatas=[{
                "name": name,
                "category": category,
                "effectiveness": effectiveness,
                "tags": json.dumps(tags)
            }]
        )

    def search(self, query_text, n=3):
        results = self.collection.query(query_texts=[query_text], n_results=n)
        out = []
        if results and results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                out.append({
                    "id": results["ids"][0][i],
                    "name": meta.get("name", "Unknown"),
                    "cat": meta.get("category", "general"),
                    "desc": doc,
                    "eff": meta.get("effectiveness", 0.8),
                    "tags": json.loads(meta.get("tags", "[]"))
                })
        return out

    def get_stats(self):
        return {"total_techniques": self.collection.count(), "persist_dir": CHROMA_DIR}

def init_default_techniques(db=None):
    d = db or KiratorVectorDB()
    techs = [
        ("cot", "Chain-of-Thought", "reasoning", "Step-by-step reasoning for complex problems", ["logic","steps","reasoning","analyze","think","explain"], 0.92),
        ("fewshot", "Few-Shot Learning", "learning", "Provide examples to guide output format", ["examples","pattern","format","similar","sample"], 0.89),
        ("role", "Role Assignment", "persona", "Assign expert persona for specialized knowledge", ["expert","persona","role","specialist","professional"], 0.85),
        ("struct", "Structured Output", "formatting", "Enforce specific output format like JSON", ["json","schema","structured","output","format"], 0.88),
        ("constraints", "Constraint Specification", "control", "Explicit boundaries and requirements", ["must","avoid","limit","requirement","rule"], 0.84),
        ("reflection", "Self-Reflection", "reasoning", "Model evaluates its own thinking before answering", ["check","verify","review","validate","critique"], 0.86),
    ]
    for t in techs:
        d.add_technique(t[0], t[1], t[2], t[3], t[4], t[5])
    return d.get_stats()

