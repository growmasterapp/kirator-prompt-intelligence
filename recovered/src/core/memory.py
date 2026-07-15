"""
Session-scoped conversation memory for Kirator Prompt Factory.

Stores pipeline turn history so that follow-up requests like:
  1. "Build me a Discord bot"
  2. "Add multiplayer support"
...are understood as continuations of the same project.

Memory is NOT persistent across sessions unless explicitly saved.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TurnRecord:
    """A single pipeline turn stored in memory."""

    turn_number: int
    request_text: str
    classification: Optional[dict] = None  # RequestClassification as dict
    intent: Optional[dict] = None  # IntentAnalysis as dict
    difficulty: Optional[dict] = None  # DifficultyAssessment as dict
    strategy: Optional[dict] = None  # PromptStrategy as dict
    composed_prompt: str = ""
    quality_score: Optional[int] = None
    timestamp: float = field(default_factory=time.time)

    def to_context_summary(self) -> str:
        """Produce a brief summary for injecting into the next turn's context."""
        parts = [f"[Turn {self.turn_number}] Request: {self.request_text}"]
        if self.classification:
            parts.append(f"  Category: {self.classification.get('task_category', 'unknown')}")
        if self.intent:
            parts.append(f"  Intent: {self.intent.get('primary_intent', 'unknown')}")
            domains = self.intent.get("domain_knowledge_required", [])
            if domains:
                parts.append(f"  Domains: {', '.join(domains)}")
        if self.strategy:
            techs = self.strategy.get("selected_techniques", [])
            if techs:
                names = [t.get("name", t) if isinstance(t, dict) else str(t) for t in techs]
                parts.append(f"  Techniques used: {', '.join(names[:5])}")
        if self.quality_score is not None:
            parts.append(f"  Quality: {self.quality_score}/100")
        return "\n".join(parts)


class SessionMemory:
    """
    In-memory session-scoped conversation store.

    One instance per session_id. Stores a list of TurnRecords and provides
    methods to build context for the pipeline.
    """

    def __init__(self, session_id: Optional[str] = None, max_turns: int = 50):
        self.session_id = session_id
        self.max_turns = max_turns
        self._turns: list[TurnRecord] = []
        self._created_at = time.time()

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def add_turn(
        self,
        request_text: str,
        classification=None,
        intent=None,
        difficulty=None,
        strategy=None,
        composed_prompt: str = "",
        quality_score: Optional[int] = None,
    ) -> TurnRecord:
        """Record a completed pipeline turn."""
        turn = TurnRecord(
            turn_number=len(self._turns) + 1,
            request_text=request_text,
            classification=self._to_dict(classification),
            intent=self._to_dict(intent),
            difficulty=self._to_dict(difficulty),
            strategy=self._to_dict(strategy),
            composed_prompt=composed_prompt,
            quality_score=quality_score,
        )
        self._turns.append(turn)

        # Evict oldest if over limit
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns:]

        logger.debug(f"[Memory] Session {self.session_id}: turn {turn.turn_number} recorded")
        return turn

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_context(self, max_turns: int = 5) -> str:
        """
        Build a context string from recent turns for injection into
        the next pipeline run. Used by stages 2-6 to understand continuity.
        """
        if not self._turns:
            return ""

        recent = self._turns[-max_turns:]
        lines = [
            "## CONVERSATION HISTORY (previous turns in this session)",
            "The user has been working through a multi-step project. Here is the context:",
            "",
        ]
        for turn in recent:
            lines.append(turn.to_context_summary())
            lines.append("")

        return "\n".join(lines)

    def get_last_turn(self) -> Optional[TurnRecord]:
        """Return the most recent turn, or None."""
        return self._turns[-1] if self._turns else None

    def get_turn_count(self) -> int:
        return len(self._turns)

    def is_continuation(self, current_request: str) -> bool:
        """
        Heuristic: is this request a continuation of the previous one?

        Checks for:
        - Reference words (it, that, this, above, previous, same)
        - Modification words (add, change, update, improve, modify, extend)
        - Short requests (< 15 words) following a longer one
        """
        if not self._turns:
            return False

        lower = current_request.lower().strip()
        word_count = len(lower.split())

        # Short follow-up commands
        continuation_words = [
            "add", "also", "too", "extend", "update", "change", "modify",
            "improve", "fix", "remove", "delete", "instead", "but",
            "however", "now", "next", "then", "and", "plus",
            "make it", "can you", "what about", "how about",
        ]
        reference_words = [
            "it", "that", "this", "the above", "the previous", "same",
            "the bot", "the function", "the code", "the prompt",
            "the app", "the site", "the page",
        ]

        has_continuation = any(lower.startswith(w) for w in continuation_words)
        has_reference = any(f" {w} " in f" {lower} " for w in reference_words)

        # Short requests are only continuations if they ALSO use
        # continuation/reference language — not just because they're brief.
        is_short_followup = (
            word_count <= 12
            and self._turns[-1].request_text != current_request
            and (has_continuation or has_reference)
        )

        return is_short_followup or has_continuation or has_reference

    def get_domain_continuity(self) -> list[str]:
        """Return domains from recent turns for context continuity."""
        domains = []
        for turn in self._turns[-3:]:
            if turn.intent and "domain_knowledge_required" in turn.intent:
                for d in turn.intent["domain_knowledge_required"]:
                    if d not in domains:
                        domains.append(d)
        return domains

    # ------------------------------------------------------------------
    # SERIALIZE / DESERIALIZE
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize session for potential persistence."""
        return {
            "session_id": self.session_id,
            "created_at": self._created_at,
            "turn_count": len(self._turns),
            "turns": [
                {
                    "turn_number": t.turn_number,
                    "request_text": t.request_text,
                    "classification": t.classification,
                    "intent": t.intent,
                    "quality_score": t.quality_score,
                    "timestamp": t.timestamp,
                }
                for t in self._turns
            ],
        }

    def clear(self) -> None:
        """Wipe session memory."""
        self._turns.clear()

    @staticmethod
    def _to_dict(obj) -> Optional[dict]:
        """Convert a Pydantic model or dict to dict for storage."""
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        return None


class MemoryManager:
    """
    Manages multiple SessionMemory instances.

    Provides a global access point for creating, retrieving, and
    cleaning up session memories.
    """

    def __init__(self, default_max_turns: int = 50):
        self._sessions: dict[str, SessionMemory] = {}
        self._default_max = default_max_turns

    def get_session(self, session_id: str) -> SessionMemory:
        """Get or create a session memory."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(
                session_id=session_id, max_turns=self._default_max
            )
        return self._sessions[session_id]

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def active_sessions(self) -> int:
        return len(self._sessions)

    def clear_all(self) -> None:
        self._sessions.clear()


# Global singleton
_global_memory = MemoryManager()


def get_memory_manager() -> MemoryManager:
    """Return the global MemoryManager instance."""
    return _global_memory