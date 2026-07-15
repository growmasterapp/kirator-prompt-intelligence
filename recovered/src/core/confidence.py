"""
Confidence Transparency System for Kirator Prompt Factory.

Tracks confidence/reliability signals from every pipeline stage and
produces a unified confidence report. Helps users understand WHERE
the pipeline was uncertain and whether the output is trustworthy.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class StageSignal:
    """A single confidence signal from one pipeline stage."""
    stage: str          # e.g. "S1 Router"
    signal_name: str    # e.g. "classification_confidence"
    value: float        # 0.0-1.0 normalized
    raw_value: any = None  # original value before normalization
    timestamp: float = field(default_factory=time.time)
    notes: str = ""


class ConfidenceTracker:
    """
    Collects and aggregates confidence signals across all pipeline stages.

    Usage:
        tracker = ConfidenceTracker()
        tracker.add_signal("S1 Router", "classification_confidence", 0.92)
        tracker.add_signal("S2 Intent", "intent_confidence", 0.85)
        ...
        report = tracker.get_report()
        print(report["overall_confidence"])  # weighted average
        print(report["weakest_stage"])       # which stage was least confident
    """

    def __init__(self):
        self._signals: list[StageSignal] = []

    def add_signal(self, stage: str, signal_name: str, value: float,
                   raw_value=None, notes: str = "") -> None:
        """Record a confidence signal from a pipeline stage."""
        # Normalize to 0-1
        normalized = min(1.0, max(0.0, float(value)))
        if raw_value is not None and isinstance(raw_value, (int, float)) and raw_value > 1.0:
            # Score is 0-100, normalize to 0-1
            normalized = raw_value / 100.0

        signal = StageSignal(
            stage=stage,
            signal_name=signal_name,
            value=normalized,
            raw_value=raw_value if raw_value is not None else value,
            timestamp=time.time(),
            notes=notes,
        )
        self._signals.append(signal)
        logger.debug(f"[Confidence] {stage}: {signal_name} = {normalized:.3f}")

    def get_signals(self) -> list[StageSignal]:
        return list(self._signals)

    def get_overall_confidence(self) -> float:
        """
        Calculate overall pipeline confidence as a weighted average.

        Weights reflect each stage's impact on final output quality:
          - S2 Intent:     0.25  (most important — if we misunderstand the request, nothing else matters)
          - S4 Strategy:   0.20  (technique selection drives prompt quality)
          - S7 Critic:     0.20  (direct quality assessment)
          - S8 Optimizer:  0.15  (final quality after refinement)
          - S3 Difficulty: 0.10  (affects technique and length choices)
          - S1 Router:     0.10  (classification affects strategy)
        """
        if not self._signals:
            return 0.0

        stage_weights = {
            "S1 Router": 0.10,
            "S2 Intent": 0.25,
            "S3 Difficulty": 0.10,
            "S4 Strategy": 0.20,
            "S7 Critic": 0.20,
            "S8 Optimizer": 0.15,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for signal in self._signals:
            weight = stage_weights.get(signal.stage, 0.05)
            weighted_sum += signal.value * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def get_weakest_stage(self) -> Optional[StageSignal]:
        """Return the signal with the lowest confidence."""
        if not self._signals:
            return None
        return min(self._signals, key=lambda s: s.value)

    def get_strongest_stage(self) -> Optional[StageSignal]:
        """Return the signal with the highest confidence."""
        if not self._signals:
            return None
        return max(self._signals, key=lambda s: s.value)

    def get_report(self) -> dict:
        """
        Produce the full confidence transparency report.

        Returns dict with:
          - overall_confidence: float (0-1)
          - overall_percent: int (0-100)
          - grade: str (A/B/C/D/F)
          - stage_breakdown: list of dicts
          - weakest_stage: dict or None
          - strongest_stage: dict or None
          - recommendations: list of str
          - signal_count: int
        """
        overall = self.get_overall_confidence()
        weakest = self.get_weakest_stage()
        strongest = self.get_strongest_stage()

        # Grade mapping
        if overall >= 0.85:
            grade = "A"
        elif overall >= 0.70:
            grade = "B"
        elif overall >= 0.55:
            grade = "C"
        elif overall >= 0.40:
            grade = "D"
        else:
            grade = "F"

        # Stage breakdown
        stage_breakdown = []
        for s in self._signals:
            stage_breakdown.append({
                "stage": s.stage,
                "signal": s.signal_name,
                "confidence": round(s.value, 3),
                "raw": s.raw_value,
                "notes": s.notes,
            })

        # Recommendations based on weak signals
        recommendations = []
        if weakest and weakest.value < 0.6:
            recommendations.append(
                f"Low confidence at {weakest.stage} ({weakest.signal_name}: {weakest.value:.0%}). "
                f"Consider rephrasing your request for clarity."
            )
        if weakest and weakest.stage == "S7 Critic" and weakest.value < 0.7:
            recommendations.append(
                "Quality evaluation was uncertain. The optimized prompt may benefit from manual review."
            )
        if overall < 0.6:
            recommendations.append(
                "Overall pipeline confidence is below 60%. The output may not fully match your intent."
            )
        if len(self._signals) >= 4:
            # Check for large variance between stages
            values = [s.value for s in self._signals]
            variance = sum((v - overall) ** 2 for v in values) / len(values)
            if variance > 0.05:
                recommendations.append(
                    "High variance between stage confidences suggests inconsistent processing."
                )

        return {
            "overall_confidence": round(overall, 3),
            "overall_percent": round(overall * 100),
            "grade": grade,
            "stage_breakdown": stage_breakdown,
            "weakest_stage": {
                "stage": weakest.stage,
                "signal": weakest.signal_name,
                "confidence": round(weakest.value, 3),
            } if weakest else None,
            "strongest_stage": {
                "stage": strongest.stage,
                "signal": strongest.signal_name,
                "confidence": round(strongest.value, 3),
            } if strongest else None,
            "recommendations": recommendations,
            "signal_count": len(self._signals),
        }

    def clear(self) -> None:
        self._signals.clear()