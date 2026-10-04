import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.models import IntentAnalysis
from src.core.exceptions import reraise_if_cancelled
from src.core.json_utils import extract_json, parse_json_with_retry
from src.models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

class IntentAnalyzer:
    def __init__(self, llm_client):
        self.llm = llm_client

    def process(self, request, context):
        prompt = """Analyze the following user request and return ONLY valid JSON with this exact structure:
{"primary_intent": "one of: code_generation|creative_writing|data_analysis|business_planning|research|troubleshooting|explanation|other",
"secondary_intents": ["list of 0-3 secondary goals"],
"domain_knowledge_required": ["list of domains needed"],
"constraints_identified": ["any explicit constraints mentioned"],
"ambiguity_score": 0.0to1.0,
"clarification_questions": ["0-2 questions if ambiguous"],
"confidence": 0.0to1.0}

USER REQUEST: """ + request

        try:
            raw = self.llm.generate(prompt)
            data = parse_json_with_retry(raw, max_retries=2)
            return IntentAnalysis(
                primary_intent=data.get("primary_intent", "general"),
                secondary_intents=data.get("secondary_intents", []),
                domain_knowledge_required=data.get("domain_knowledge_required", []),
                constraints_identified=data.get("constraints_identified", []),
                ambiguity_score=float(data.get("ambiguity_score", 0.5)),
                clarification_questions=data.get("clarification_questions", []),
                confidence=float(data.get("confidence", 0.75))
            )
        except Exception as e:
            reraise_if_cancelled(e)
            logger.error(f"Intent analysis failed: {e}")

        return IntentAnalysis(
            primary_intent="general",
            secondary_intents=[],
            domain_knowledge_required=[],
            constraints_identified=[],
            ambiguity_score=0.5,
            clarification_questions=[],
            confidence=0.6
        )

    def get_stage_info(self):
        return {"name": "Intent Analyzer", "stage": 2}