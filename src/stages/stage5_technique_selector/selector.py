"""
Stage 5: Technique Selector

Uses ChromaDB (via embeddings) as the primary search method.
Falls back to in-memory keyword matching when ChromaDB is unavailable.
Maintains a catalog of 24 prompting techniques with rich metadata.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)

# ================================================================
# COMPLETE TECHNIQUE CATALOG (24 techniques)
# Each entry: (id, name, category, description, search_tags, effectiveness 0-1)
# ================================================================

TECHNIQUE_CATALOG = [
    # --- REASONING ---
    (
        "cot",
        "Chain-of-Thought",
        "reasoning",
        "Step-by-step reasoning that breaks complex problems into intermediate steps before reaching a conclusion. Forces the model to show its work.",
        ["logic", "steps", "reasoning", "analyze", "think", "step", "process", "how", "explain", "why", "derive", "calculate", "prove"],
        0.92,
    ),
    (
        "tot",
        "Tree-of-Thought",
        "reasoning",
        "Explores multiple reasoning paths simultaneously, evaluating each branch before selecting the best solution. Good for problems with multiple valid approaches.",
        ["explore", "branches", "alternatives", "compare approaches", "evaluate options", "multiple solutions", "decision tree"],
        0.88,
    ),
    (
        "reflection",
        "Self-Reflection",
        "reasoning",
        "Model evaluates its own thinking process before answering, catching errors and improving accuracy through self-critique.",
        ["check", "verify", "review", "improve", "double", "confirm", "validate", "critique", "self-check", "ensure"],
        0.86,
    ),
    (
        "socratic",
        "Socratic Questioning",
        "reasoning",
        "Uses a series of probing questions to guide deeper thinking and expose assumptions, leading to more thorough analysis.",
        ["question", "probe", "assumption", "challenge", "dig deeper", "examine", "what if", "why is that"],
        0.82,
    ),
    (
        "analogical",
        "Analogical Reasoning",
        "reasoning",
        "Solves problems by drawing parallels to well-understood analogous situations, then transferring insights to the current problem.",
        ["like", "similar to", "analogy", "compare to", "just as", "parallel", "metaphor", "analogy with", "reminds me of"],
        0.83,
    ),

    # --- LEARNING ---
    (
        "fewshot",
        "Few-Shot Learning",
        "learning",
        "Provide concrete examples of the desired input/output pattern so the model can generalize to new cases. Most effective for format-sensitive tasks.",
        ["examples", "pattern", "format", "like", "similar", "follow", "sample", "instance", "template", "demonstration"],
        0.89,
    ),
    (
        "zeroshot",
        "Zero-Shot with Instructions",
        "learning",
        "Relies purely on clear instructions without examples. Works well when the task is straightforward and the model has relevant pre-trained knowledge.",
        ["direct", "simple", "straightforward", "just do", "no example", "explain", "describe", "define"],
        0.78,
    ),
    (
        "cot_fewshot",
        "Chain-of-Thought + Few-Shot",
        "learning",
        "Combines step-by-step reasoning with worked examples. Shows the model both HOW to think and WHAT the expected output looks like.",
        ["examples with reasoning", "worked example", "step by step example", "show your work", "walkthrough"],
        0.91,
    ),

    # --- PERSONA ---
    (
        "role",
        "Role Assignment",
        "persona",
        "Assign an expert persona (e.g. senior engineer, domain specialist) to leverage specialized knowledge and appropriate tone.",
        ["expert", "persona", "role", "act as", "you are", "specialist", "professional", "senior", "junior", "consultant", "advisor"],
        0.85,
    ),
    (
        "audience",
        "Audience Targeting",
        "persona",
        "Explicitly defines the target reader/audience so the model adjusts vocabulary, depth, tone, and assumed knowledge level.",
        ["audience", "reader", "beginner", "non-technical", "executive", "stakeholder", "child", "student", "professional"],
        0.81,
    ),

    # --- FORMATTING ---
    (
        "struct",
        "Structured Output",
        "formatting",
        "Enforces a specific output format such as JSON, table, or schema. Critical for machine-readable results and API integrations.",
        ["json", "schema", "structured", "output", "format", "csv", "table", "list", "markdown", "yaml", "xml"],
        0.88,
    ),
    (
        "markdown",
        "Markdown Formatting",
        "formatting",
        "Requests output formatted with Markdown headers, bullet points, code blocks, and tables for readability and documentation.",
        ["markdown", "headers", "document", "report", "readable", "formatted", "sections", "chapters"],
        0.80,
    ),

    # --- CONTROL ---
    (
        "constraints",
        "Constraint Specification",
        "control",
        "Explicit boundaries and requirements: what the model must do and must avoid. Reduces unwanted outputs and hallucinations.",
        ["must", "should", "avoid", "cannot", "limit", "requirement", "rule", "only", "never", "always", "don't", "restrict"],
        0.84,
    ),
    (
        "negative",
        "Negative Prompting",
        "control",
        "Explicitly tells the model what NOT to do, which is often more effective than only stating what it should do.",
        ["don't", "avoid", "never", "do not", "skip", "exclude", "without", "no", "refrain", "ignore"],
        0.76,
    ),
    (
        "length",
        "Length Control",
        "control",
        "Specifies exact or approximate output length (word count, paragraph count, token budget) to control verbosity.",
        ["short", "concise", "brief", "detailed", "comprehensive", "word count", "paragraph", "length", "summary", "expand"],
        0.79,
    ),

    # --- DECOMPOSITION ---
    (
        "decompose",
        "Task Decomposition",
        "decomposition",
        "Breaks a complex task into smaller sub-tasks that are handled sequentially. Prevents the model from being overwhelmed.",
        ["break down", "step by step", "phase", "part", "first then", "sequential", "divide", "split", "sub-task", "milestone"],
        0.90,
    ),
    (
        "plan_execute",
        "Plan-and-Execute",
        "decomposition",
        "First creates a high-level plan, then executes each step. Separates planning from execution for complex multi-step tasks.",
        ["plan", "roadmap", "outline", "then implement", "strategy", "approach", "blueprint", "design first"],
        0.87,
    ),

    # --- QUALITY ---
    (
        "verification",
        "Output Verification",
        "quality",
        "Asks the model to verify its own output against the original requirements, checking for completeness and correctness.",
        ["verify", "check", "validate", "test", "confirm", "ensure complete", "review output", "quality check"],
        0.83,
    ),
    (
        "iteration",
        "Iterative Refinement",
        "quality",
        "Generates an initial output, then refines it through one or more improvement passes based on specific criteria.",
        ["refine", "improve", "iterate", "revise", "polish", "enhance", "optimize", "better", "revise"],
        0.85,
    ),
    (
        "edge_cases",
        "Edge Case Handling",
        "quality",
        "Explicitly instructs the model to consider edge cases, boundary conditions, and unusual inputs that might break the solution.",
        ["edge case", "boundary", "corner case", "what if", "exception", "error handling", "edge", "unusual", "edge condition"],
        0.80,
    ),

    # --- CREATIVE ---
    (
        "creative",
        "Creative Freedom",
        "creative",
        "Gives the model creative latitude with minimal constraints, useful for brainstorming, storytelling, and ideation.",
        ["creative", "brainstorm", "ideas", "imagine", "innovate", "explore", "possibilities", "inspire", "generate ideas"],
        0.77,
    ),
    (
        "style",
        "Style Imitation",
        "creative",
        "Instructs the model to match a specific writing style, tone, or voice. Useful for maintaining brand consistency.",
        ["style", "tone", "voice", "formal", "casual", "humorous", "professional", "academic", "conversational"],
        0.78,
    ),

    # --- SECURITY ---
    (
        "security",
        "Security Constraints",
        "security",
        "Adds security-focused constraints to prevent injection, PII leakage, or unsafe outputs. Essential for production prompts.",
        ["security", "safe", "sanitize", "inject", "pii", "sensitive", "privacy", "protect", "vulnerable", "xss", "sql injection"],
        0.81,
    ),

    # --- META ---
    (
        "meta_prompt",
        "Meta-Prompting",
        "meta",
        "Uses the model to generate or improve prompts itself. The model acts as a prompt engineer, creating better prompts for downstream use.",
        ["meta", "generate prompt", "write a prompt", "create prompt", "prompt engineering", "improve this prompt"],
        0.84,
    ),
]


def _build_search_index(catalog: list[tuple]) -> dict[str, dict]:
    """Convert the catalog tuple list into a dict keyed by id for fast lookup."""
    index = {}
    for item in catalog:
        tech_id, name, category, description, tags, effectiveness = item
        index[tech_id] = {
            "id": tech_id,
            "name": name,
            "cat": category,
            "desc": description,
            "eff": effectiveness,
            "tags": tags,
        }
    return index


class TechniqueSelector:
    """
    Selects the most relevant prompting techniques for a given request.

    Primary method: ChromaDB semantic search (via embeddings).
    Fallback method: in-memory keyword matching against technique tags.
    """

    def __init__(self, embedder: EmbeddingClient | None = None, use_chromadb: bool = True):
        self.embedder = embedder
        self.catalog = _build_search_index(TECHNIQUE_CATALOG)
        self._db = None
        self._chromadb_ready = False

        if use_chromadb and embedder is not None:
            self._init_chromadb()

    def _init_chromadb(self) -> None:
        """Attempt to initialize ChromaDB with the full technique catalog."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            # Persist next to the project data directory
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "data", "chroma_techniques",
            )
            os.makedirs(db_path, exist_ok=True)

            client = chromadb.PersistentClient(path=db_path)
            self._collection = client.get_or_create_collection(
                name="techniques",
                metadata={"description": "Prompting techniques library v2"},
            )

            # Seed ChromaDB if empty
            if self._collection.count() == 0:
                ids = []
                documents = []
                metadatas = []
                for tech in TECHNIQUE_CATALOG:
                    tech_id, name, category, description, tags, effectiveness = tech
                    ids.append(tech_id)
                    documents.append(description)
                    metadatas.append({
                        "name": name,
                        "category": category,
                        "effectiveness": float(effectiveness),
                        "tags": ",".join(tags),
                    })
                self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                logger.info(f"Seeded ChromaDB with {len(ids)} techniques")

            self._chromadb_ready = True
            logger.info("ChromaDB technique store initialized")

        except Exception as e:
            logger.warning(f"ChromaDB unavailable, using keyword fallback: {e}")
            self._chromadb_ready = False

    def search(self, query_text: str, n: int = 5) -> list[dict]:
        """
        Search for the top-N most relevant techniques.

        Uses ChromaDB semantic search when available,
        falls back to keyword tag matching otherwise.
        """
        if self._chromadb_ready:
            return self._search_chromadb(query_text, n)
        return self._search_keyword(query_text, n)

    def _search_chromadb(self, query_text: str, n: int) -> list[dict]:
        """Semantic search via ChromaDB collection query."""
        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(n, self._collection.count()),
            )
            out = []
            if results and results["documents"] and results["documents"][0]:
                for i, _doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i]
                    distance = results["distances"][0][i] if "distances" in results else None
                    tech_id = results["ids"][0][i]
                    # Enrich with full catalog data
                    catalog_entry = self.catalog.get(tech_id, {})
                    out.append({
                        "id": tech_id,
                        "name": meta.get("name", catalog_entry.get("name", "Unknown")),
                        "cat": meta.get("category", catalog_entry.get("cat", "general")),
                        "desc": catalog_entry.get("desc", _doc if _doc else ""),
                        "eff": meta.get("effectiveness", catalog_entry.get("eff", 0.8)),
                        "tags": catalog_entry.get("tags", meta.get("tags", "").split(",")),
                        "distance": distance,
                    })
            return out if out else self._search_keyword(query_text, n)
        except Exception as e:
            from src.core.exceptions import reraise_if_cancelled
            reraise_if_cancelled(e)
            logger.warning(f"ChromaDB search failed, falling back to keywords: {e}")
            return self._search_keyword(query_text, n)

    def _search_keyword(self, query_text: str, n: int) -> list[dict]:
        """Fallback: rank techniques by keyword overlap with their tags."""
        query_lower = query_text.lower()
        results = []
        for tech_id, tech in self.catalog.items():
            score = sum(1 for tag in tech["tags"] if tag.lower() in query_lower)
            if score > 0:
                results.append((tech, score))
        results.sort(key=lambda x: x[1], reverse=True)
        if not results:
            # Return top techniques by effectiveness as fallback
            sorted_by_eff = sorted(self.catalog.values(), key=lambda t: t["eff"], reverse=True)
            return sorted_by_eff[:n]
        return [r[0] for r in results[:n]]

    def get_technique_by_id(self, tech_id: str) -> dict | None:
        """Look up a single technique by its ID."""
        return self.catalog.get(tech_id)

    def get_all_techniques(self) -> list[dict]:
        """Return the full catalog (useful for the plugin system later)."""
        return list(self.catalog.values())

    def get_stage_info(self) -> dict:
        return {"name": "Technique Selector", "stage": 5}