"""
Sample Analyzer Plugin: Code-Specific Intent Analyzer

Provides deeper analysis for code-related requests by detecting
specific programming patterns, frameworks, and libraries.
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.plugins.base import KiratorPlugin, kirator_plugin


@kirator_plugin(
    plugin_type="analyzer",
    plugin_id="analyzer_code_deep",
    name="Deep Code Analyzer",
    version="1.0.0",
    description="Enriches intent analysis for code requests by detecting specific languages, frameworks, and patterns.",
    author="Kirator Team",
)
class DeepCodeAnalyzer(KiratorPlugin):

    LANGUAGE_PATTERNS = {
        "python": ["python", "django", "flask", "fastapi", "pandas", "numpy", "pytorch", "asyncio"],
        "javascript": ["javascript", "typescript", "node", "express", "react", "vue", "angular", "next.js", "deno"],
        "java": ["java", "spring", "maven", "gradle", "jvm", "kotlin"],
        "rust": ["rust", "cargo", "tokio", "actix", "serde"],
        "go": ["go ", "golang", "gin", "goroutine", "go.mod"],
        "sql": ["sql", "query", "select", "join", "postgres", "mysql", "sqlite", "database"],
    }

    FRAMEWORK_PATTERNS = {
        "web_frontend": ["react", "vue", "angular", "svelte", "next.js", "nuxt", "gatsby", "tailwind", "html", "css"],
        "web_backend": ["flask", "django", "fastapi", "express", "spring", "rails", "laravel", "api", "rest", "graphql"],
        "data_science": ["pandas", "numpy", "matplotlib", "scikit", "tensorflow", "pytorch", "jupyter", "analysis"],
        "devops": ["docker", "kubernetes", "terraform", "ci/cd", "github actions", "jenkins", "aws", "azure"],
    }

    def activate(self):
        pass

    def deactivate(self):
        pass

    def analyze_intent(self, request: str, context: dict):
        """Enrich intent with code-specific metadata. Returns dict or None."""
        lower = request.lower()

        # Only activate for code-related requests
        code_keywords = ["write", "create", "build", "implement", "code", "function", "class", "api", "app", "script", "program", "module", "bot"]
        if not any(kw in lower for kw in code_keywords):
            return None  # Not a code request, defer to default

        detected_languages = []
        for lang, keywords in self.LANGUAGE_PATTERNS.items():
            if any(kw in lower for kw in keywords):
                detected_languages.append(lang)

        detected_frameworks = []
        for framework, keywords in self.FRAMEWORK_PATTERNS.items():
            if any(kw in lower for kw in keywords):
                detected_frameworks.append(framework)

        if not detected_languages and not detected_frameworks:
            return None  # No code specifics detected

        return {
            "detected_languages": detected_languages,
            "detected_frameworks": detected_frameworks,
            "is_code_request": True,
            "enrichment_source": "analyzer_code_deep",
        }