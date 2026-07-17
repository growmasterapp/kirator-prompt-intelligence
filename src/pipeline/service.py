"""
PipelineService — orchestrates the 9-stage prompt intelligence pipeline.

Extracted from the GUI layer so the pipeline is testable, cancellable,
and reusable by future agents/CLI/API surfaces.
"""

from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from src.core.config import get_settings
from src.core.exceptions import PipelineCancelled
from src.core.history_store import HistoryStore
from src.core.logging_setup import get_logger
from src.core.models import TechniqueMetadata
from src.core.target_profiles import get_target_profile

logger = get_logger(__name__)


class PipelineService:
    """Thread-safe single-job pipeline runner with progress + cancel."""

    def __init__(self, history: HistoryStore | None = None):
        self.settings = get_settings()
        self.history = history or HistoryStore()
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._state: dict[str, Any] = self._idle_state()

    @staticmethod
    def _idle_state() -> dict[str, Any]:
        return {
            "status": "idle",
            "current_stage": "",
            "stage_progress": {},
            "log_messages": [],
            "result": None,
            "start_time": None,
            "error": None,
            "request_hash": None,
            "cancelled": False,
        }

    # ------------------------------------------------------------------
    # Progress helpers
    # ------------------------------------------------------------------

    def add_log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        with self._lock:
            self._state["log_messages"].append(line)
        logger.info(msg)

    def set_stage(self, num: int, name: str, detail: str, elapsed: float) -> None:
        with self._lock:
            self._state["current_stage"] = str(num)
            self._state["stage_progress"][str(num)] = {
                "name": name,
                "detail": detail,
                "time": round(elapsed, 1),
            }

    def _check_cancel(self) -> None:
        if self._cancel_event.is_set():
            raise PipelineCancelled("Pipeline cancelled by user")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self._state["status"],
                "current_stage": self._state["current_stage"],
                "stages": dict(self._state["stage_progress"]),
                "recent_logs": list(self._state["log_messages"][-12:]),
                "error": self._state.get("error"),
                "cancelled": self._state.get("cancelled", False),
            }

    def consume_terminal(self) -> dict[str, Any] | None:
        """Return and clear a completed/error/cancelled result (one-shot for polling)."""
        with self._lock:
            status = self._state["status"]
            if status not in ("complete", "error", "cancelled"):
                return None
            result = self._state.get("result")
            error = self._state.get("error")
            logs = list(self._state["log_messages"][-20:])
            payload = {
                "status": status,
                "result": result,
                "error": error,
                "recent_logs": logs,
            }
            self._state = self._idle_state()
            return payload

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        with self._lock:
            return self._state["status"] == "running"

    def start(self, request_text: str, target_model: str = "generic") -> dict[str, Any]:
        request_text = (request_text or "").strip()
        if not request_text:
            return {"ok": False, "error": "No request provided", "code": 400}

        profile = get_target_profile(target_model)
        target_model = profile.id

        with self._lock:
            if self._state["status"] == "running":
                return {
                    "ok": False,
                    "error": "Pipeline already running",
                    "code": 409,
                    "message": "Please wait for the current run to finish or cancel it.",
                }

            last_hash = self._state.get("request_hash")
            start_time = self._state.get("start_time")
            req_hash = hash(request_text)
            if (
                last_hash == req_hash
                and start_time
                and (time.time() - start_time) < self.settings.pipeline.poll_dedupe_seconds
            ):
                return {
                    "ok": False,
                    "error": "Duplicate request detected",
                    "code": 429,
                    "message": "You just submitted this request. Please wait.",
                }

            self._cancel_event.clear()
            self._state = {
                "status": "running",
                "current_stage": "",
                "stage_progress": {},
                "log_messages": [],
                "result": None,
                "start_time": time.time(),
                "error": None,
                "request_hash": req_hash,
                "cancelled": False,
            }

        self._worker = threading.Thread(
            target=self._run,
            args=(request_text, target_model),
            daemon=True,
            name="kirator-pipeline",
        )
        self._worker.start()
        return {
            "ok": True,
            "status": "started",
            "target_model": target_model,
            "message": "Pipeline started successfully",
            "note": "This may take 1–3 minutes depending on complexity",
        }

    def cancel(self) -> dict[str, Any]:
        with self._lock:
            if self._state["status"] != "running":
                return {
                    "status": "idle",
                    "message": "No pipeline is currently running",
                }
        self._cancel_event.set()
        self.add_log("Cancel requested — stopping after current stage…")
        return {
            "status": "cancel_requested",
            "message": "Cancellation requested. The run will stop between stages.",
        }

    # ------------------------------------------------------------------
    # Stage execution
    # ------------------------------------------------------------------

    def _run(self, request_text: str, target_model: str) -> None:
        T = time.time()
        profile = get_target_profile(target_model)
        self.add_log("=" * 50)
        self.add_log("PIPELINE STARTED")
        self.add_log(f"Request: {request_text[:80]}")
        self.add_log(f"Target model: {profile.name}")
        if profile.hint:
            self.add_log(f"Model hint: {profile.hint}")
        self.add_log("=" * 50)

        try:
            self._check_cancel()
            self.add_log("[INIT] Importing modules…")
            from src.models.ollama_client import OllamaClient
            from src.models.embedding_client import EmbeddingClient
            from src.stages.stage1_router.router import RequestRouter
            from src.stages.stage2_intent_analyzer.analyzer import IntentAnalyzer
            from src.stages.stage3_difficulty_analyzer.analyzer import DifficultyAnalyzer
            from src.stages.stage4_strategy_planner.planner import StrategyPlanner
            from src.stages.stage5_technique_selector.selector import TechniqueSelector
            from src.stages.stage6_prompt_composer.composer import PromptComposer
            from src.stages.stage7_prompt_critic.critic import PromptCritic
            from src.stages.stage8_optimizer.optimizer import PromptOptimizer
            from src.stages.stage9_renderer.renderer import PromptRenderer

            self.add_log("[INIT] Initializing clients…")
            ollama = self.settings.ollama
            embedder = EmbeddingClient()
            reasoning = OllamaClient(
                base_url=ollama.base_url, default_model=ollama.reasoning_model
            )
            composition = OllamaClient(
                base_url=ollama.base_url, default_model=ollama.composition_model
            )

            s1 = RequestRouter(embedder)
            s2 = IntentAnalyzer(reasoning)
            s3 = DifficultyAnalyzer(reasoning)
            s4 = StrategyPlanner(reasoning)
            s5 = TechniqueSelector(embedder)
            s6 = PromptComposer(composition, s5)
            s7 = PromptCritic(composition)
            s8 = PromptOptimizer(composition)
            s9 = PromptRenderer()
            self.add_log("[INIT] All 9 stages ready")

            # S1
            self._check_cancel()
            t0 = time.time()
            c = s1.process(request_text, {})
            self.set_stage(
                1,
                "Router",
                f"{c.task_category.value} | {c.complexity_level.value}",
                time.time() - t0,
            )
            self.add_log(
                f"[S1] Router: {c.task_category.value} | {c.complexity_level.value}"
            )

            # S2 + S3 parallel
            self._check_cancel()
            self.add_log("[S2+S3] Running intent + difficulty in parallel…")

            def run_s2():
                t = time.time()
                return s2.process(request_text, {}), time.time() - t

            def run_s3():
                t = time.time()
                return s3.process(request_text, {}, intent=None), time.time() - t

            with ThreadPoolExecutor(max_workers=2) as pool:
                fut2 = pool.submit(run_s2)
                fut3 = pool.submit(run_s3)
                i, s2_time = fut2.result()
                d, s3_time = fut3.result()

            self._check_cancel()
            self.set_stage(
                2,
                "Intent",
                f"{i.primary_intent} | conf:{round(i.confidence, 2)}",
                s2_time,
            )
            self.add_log(
                f"[S2] Intent: {i.primary_intent} | conf:{round(i.confidence, 2)}"
            )
            self.set_stage(
                3,
                "Difficulty",
                f"{d.overall_level.value} | tech:{d.technical_complexity}/10",
                s3_time,
            )
            self.add_log(
                f"[S3] Difficulty: {d.overall_level.value} | tech:{d.technical_complexity}/10"
            )

            # S4
            self._check_cancel()
            t0 = time.time()
            self.add_log(f"[S4] Strategy planning ({ollama.reasoning_model})…")
            sr = s4.process(request_text, {}, c, i, d)
            self.set_stage(
                4,
                "Strategy",
                f"{len(sr.selected_techniques)} techniques selected",
                time.time() - t0,
            )
            for tech in sr.selected_techniques:
                self.add_log(f"      - {tech.name} ({tech.category})")

            # S5 — merge supplements into strategy
            self._check_cancel()
            t0 = time.time()
            tk = s5.search(request_text, 5)
            s4_ids = {t.id for t in sr.selected_techniques if t.id}
            merged_techniques = list(sr.selected_techniques)
            for tech_result in tk:
                tid = tech_result.get("id", "")
                if tid and tid not in s4_ids:
                    raw_score = float(tech_result.get("score", 0.7) or 0.7)
                    # Vector distances sometimes arrive as >1; clamp to model bounds.
                    if raw_score > 1.0:
                        raw_score = max(0.0, min(1.0, 1.0 / raw_score))
                    merged_techniques.append(
                        TechniqueMetadata(
                            id=tid,
                            name=tech_result.get("name", tid),
                            category=tech_result.get("cat", tech_result.get("category", "general")),
                            description=tech_result.get("desc", tech_result.get("description", "")),
                            effectiveness_score=max(0.0, min(1.0, raw_score)),
                            complexity_overhead=max(1, min(5, int(tech_result.get("overhead", 2) or 2))),
                            tags=list(tech_result.get("tags", []) or []),
                        )
                    )
                    self.add_log(
                        f"[S5]   + supplement: {tech_result.get('name', '?')} "
                        f"({tech_result.get('cat', '?')})"
                    )
                    s4_ids.add(tid)

            ordering = list(sr.technique_ordering) + [
                t.id for t in merged_techniques if t.id not in sr.technique_ordering
            ]
            sr = sr.model_copy(
                update={
                    "selected_techniques": merged_techniques,
                    "technique_ordering": ordering,
                }
            )
            self.set_stage(
                5,
                "Techniques",
                f"{len(merged_techniques)} techniques ready",
                time.time() - t0,
            )
            self.add_log(f"[S5] Techniques: {len(merged_techniques)} total (merged S4+S5)")

            # S6
            self._check_cancel()
            t0 = time.time()
            self.add_log(f"[S6] Composing prompt ({ollama.composition_model})…")
            p = s6.compose(request_text, sr, c, i, d)
            self.set_stage(6, "Compose", f"{len(p)} chars", time.time() - t0)
            self.add_log(f"[S6] Composed: {len(p)} chars")

            # S7
            self._check_cancel()
            t0 = time.time()
            self.add_log(f"[S7] PEEM evaluation ({ollama.composition_model})…")
            q = s7.evaluate(p, target_model)
            s7_weaknesses = list(q.weaknesses or [])
            s7_improvements = list(q.improvements or [])
            self.set_stage(
                7,
                "Critic",
                f"{q.overall_score}/100 | {len(s7_weaknesses)} weaknesses",
                time.time() - t0,
            )
            self.add_log(
                f"[S7] Critic: {q.overall_score}/100 | {len(s7_weaknesses)} weaknesses"
            )
            for w in s7_weaknesses:
                self.add_log(f"      Weakness: {w}")

            # S8
            self._check_cancel()
            t0 = time.time()
            threshold = self.settings.pipeline.quality_threshold
            max_iter = self.settings.pipeline.max_optimize_iterations
            self.add_log(f"[S8] Optimizing (target: {threshold}/100)…")
            r = s8.optimize(
                p,
                target_model,
                max_iterations=max_iter,
                quality_threshold=threshold,
            )
            opt = r["optimized_prompt"]
            improvement = r["final_score"] - q.overall_score
            self.set_stage(
                8,
                "Optimize",
                f"{r['final_score']}/100 ({improvement:+d} pts)",
                time.time() - t0,
            )
            self.add_log(
                f"[S8] Optimize: {r['final_score']}/100 ({improvement:+d} pts)"
            )
            if r.get("iterations_used"):
                self.add_log(
                    f"[S8] Iterations: {r['iterations_used']} | "
                    f"Converged: {r.get('converged', False)}"
                )

            # S9
            self._check_cancel()
            t0 = time.time()
            out = s9.render(
                opt,
                r["quality_report"],
                sr,
                {"total_sec": round(time.time() - T, 1)},
                "markdown",
            )
            self.set_stage(9, "Render", "complete", time.time() - t0)

            total = round(time.time() - T, 1)
            self.add_log("")
            self.add_log("=" * 50)
            self.add_log(f"PIPELINE COMPLETE in {total}s")
            self.add_log(f"FINAL SCORE: {r['final_score']}/100")
            self.add_log("=" * 50)

            report_dict = r["quality_report"]
            if hasattr(report_dict, "to_dict"):
                report_dict = report_dict.to_dict()
            if not isinstance(report_dict, dict):
                report_dict = {}

            final_weaknesses = report_dict.get("weaknesses") or s7_weaknesses
            final_improvements = (
                report_dict.get("improvements")
                or report_dict.get("suggested_improvements")
                or s7_improvements
            )
            if isinstance(final_weaknesses, str):
                final_weaknesses = [final_weaknesses]
            if isinstance(final_improvements, str):
                final_improvements = [final_improvements]
            report_dict["weaknesses"] = final_weaknesses
            report_dict["improvements"] = final_improvements

            result = {
                "request": request_text,
                "stages": {},
                "prompt": opt,
                "score": int(r["final_score"]),
                "report": report_dict,
                "rendered": out,
                "total_time": total,
                "target_model": target_model,
                "logs": [],
                "iterations_used": r.get("iterations_used", 1),
                "converged": r.get("converged", False),
            }

            with self._lock:
                result["stages"] = self._state["stage_progress"].copy()
                result["logs"] = self._state["log_messages"].copy()
                self._state["status"] = "complete"
                self._state["result"] = result

            self.history.add(
                request_text,
                int(r["final_score"]),
                total,
                target_model=target_model,
                prompt_preview=opt,
            )

        except PipelineCancelled:
            total = round(time.time() - T, 1)
            self.add_log("PIPELINE CANCELLED")
            with self._lock:
                self._state["status"] = "cancelled"
                self._state["cancelled"] = True
                self._state["error"] = "Cancelled by user"
                self._state["result"] = {
                    "error": "Cancelled by user",
                    "score": 0,
                    "prompt": "",
                    "rendered": f"Pipeline cancelled after {total}s.",
                    "total_time": total,
                    "logs": self._state["log_messages"].copy(),
                    "report": {"weaknesses": [], "improvements": []},
                    "stages": self._state["stage_progress"].copy(),
                }

        except Exception as e:
            tb = traceback.format_exc()
            self.add_log(f"FATAL ERROR: {e}")
            for line in tb.split("\n"):
                if line.strip():
                    self.add_log(f"  {line}")
            logger.exception("Pipeline failed")
            with self._lock:
                self._state["status"] = "error"
                self._state["error"] = str(e)
                self._state["result"] = {
                    "error": str(e),
                    "traceback": tb,
                    "score": 0,
                    "prompt": f"ERROR: Pipeline failed - {e}",
                    "rendered": (
                        f"Pipeline failed after {round(time.time() - T, 1)}s\n\n"
                        f"Error: {e}\n\nCheck the application log for details."
                    ),
                    "total_time": round(time.time() - T, 1),
                    "logs": self._state["log_messages"].copy(),
                    "report": {"weaknesses": [], "improvements": []},
                    "stages": self._state["stage_progress"].copy(),
                }


_service: PipelineService | None = None
_service_lock = threading.Lock()


def get_pipeline_service() -> PipelineService:
    global _service
    with _service_lock:
        if _service is None:
            _service = PipelineService()
        return _service
