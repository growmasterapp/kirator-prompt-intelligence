import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.models import DifficultyAssessment, ComplexityLevel
from src.core.json_utils import extract_json, parse_json_with_retry
from src.models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

LEVEL_MAP = {"trivial": ComplexityLevel.TRIVIAL, "simple": ComplexityLevel.SIMPLE, "moderate": ComplexityLevel.MODERATE, "complex": ComplexityLevel.COMPLEX, "expert": ComplexityLevel.EXPERT}

class DifficultyAnalyzer:
    def __init__(self, llm_client):
        self.llm = llm_client

    def process(self, request, context, intent=None):
        prompt = """Assess the difficulty of this task and return ONLY valid JSON:
{"overall_level": "one of: trivial|simple|moderate|complex|expert",
"technical_complexity": 1to10,
"domain_expertise_required": 1to10,
"ambiguity_tolerance": 1to10,
"creativity_demand": 1to10,
"estimated_steps": integer,
"risk_factors": ["list of risks"],
"confidence": 0.0to1.0}

TASK: """ + request

        try:
            raw = self.llm.generate(prompt)
            data = parse_json_with_retry(raw, max_retries=2)
            lvl = data.get("overall_level", "moderate")
            return DifficultyAssessment(
                overall_level=LEVEL_MAP.get(lvl, ComplexityLevel.MODERATE),
                technical_complexity=int(data.get("technical_complexity", 5)),
                domain_expertise_required=int(data.get("domain_expertise_required", 5)),
                ambiguity_tolerance=int(data.get("ambiguity_tolerance", 5)),
                creativity_demand=int(data.get("creativity_demand", 5)),
                estimated_steps=int(data.get("estimated_steps", 3)),
                risk_factors=data.get("risk_factors", []),
                confidence=float(data.get("confidence", 0.8))
            )
        except Exception as e:
            logger.error(f"Difficulty analysis failed: {e}")

        return DifficultyAssessment(
            overall_level=ComplexityLevel.MODERATE,
            technical_complexity=5,
            domain_expertise_required=5,
            ambiguity_tolerance=5,
            creativity_demand=5,
            estimated_steps=3,
            risk_factors=[],
            confidence=0.7
        )

    def get_stage_info(self):
        return {"name": "Difficulty Analyzer", "stage": 3}