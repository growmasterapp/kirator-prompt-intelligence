import sys, os, json, time, threading, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# CRITICAL: Set working directory to PROJECT ROOT
# This ensures all imports work exactly like test.py does!
# ============================================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))

os.chdir(_PROJECT_ROOT)
sys.path.insert(0, _PROJECT_ROOT)

print("=" * 60)
print("KIRATOR PROMPT INTELLIGENCE - GUI SERVER")
print("Working Directory:", os.getcwd())
print("Python Path[0]:", sys.path[0])
print("=" * 60)

from flask import Flask, render_template, request, jsonify
from werkzeug.serving import make_server

# Use absolute paths for template/static folders
_TEMPLATE_DIR = os.path.join(_SCRIPT_DIR, "templates")
_STATIC_DIR = os.path.join(_SCRIPT_DIR, "static")

app = Flask(__name__, 
           template_folder=_TEMPLATE_DIR, 
           static_folder=_STATIC_DIR)
app.config["SECRET_KEY"] = "kirator-gui-secret-v3"

# ============================================================
# MODEL PROFILES — Target model adaptation
# ============================================================
TARGET_MODEL_MAP = {
    "generic":  {"id": "generic",  "name": "Generic LLM"},
    "chatgpt":  {"id": "chatgpt",  "name": "ChatGPT / GPT-4",    "style": "markdown", "hint": "Use Markdown headers, explicit formatting instructions, JSON schema for structured output."},
    "claude":   {"id": "claude",   "name": "Claude / Anthropic", "style": "xml",      "hint": "Use XML tags for structure (<thinking>, <output_format>). Prefer longer context with clear sections."},
    "gemini":   {"id": "gemini",   "name": "Gemini / Google",    "style": "steps",    "hint": "Include more examples (few-shot). Clear step-by-step instructions. Prefer concise but complete."},
    "grok":     {"id": "grok",     "name": "Grok / xAI",         "style": "markdown", "hint": "Use Markdown formatting. Strong constraint listing. Clear role assignment."},
    "local":    {"id": "local",    "name": "Local Model",        "style": "simple",   "hint": "Simpler structure. Clear role assignment. Moderate length to avoid context overflow."},
}

# ============================================================
# SESSION MEMORY — Store prompt history per session
# ============================================================
session_memory = {
    "history": [],       # List of {request, score, time, timestamp}
    "max_history": 10,
}

# Shared state for progress tracking
progress_state = {
    "status": "idle",
    "current_stage": "",
    "stage_progress": {},
    "log_messages": [],
    "result": None,
    "start_time": None,
    "error": None,
    "request_hash": None,
}
state_lock = threading.Lock()
memory_lock = threading.Lock()

def add_log(msg):
    ts = time.strftime("%H:%M:%S")
    with state_lock:
        progress_state["log_messages"].append("[" + ts + "] " + msg)
    print("[PIPELINE] " + msg)

def set_stage(num, name, detail, elapsed):
    with state_lock:
        progress_state["current_stage"] = str(num)
        progress_state["stage_progress"][str(num)] = {
            "name": name, 
            "detail": detail, 
            "time": round(elapsed, 1)
        }

def add_to_history(request_text, score, total_time):
    """Add a completed prompt to session history."""
    with memory_lock:
        entry = {
            "request": request_text[:100],
            "score": score,
            "time": total_time,
            "timestamp": time.strftime("%H:%M:%S")
        }
        session_memory["history"].insert(0, entry)
        # Keep only last N entries
        if len(session_memory["history"]) > session_memory["max_history"]:
            session_memory["history"] = session_memory["history"][:session_memory["max_history"]]

def run_pipeline_bg(request_text, target_model="generic"):
    """
    Runs the full 9-stage pipeline in background thread.
    Includes all prior fixes: S7/S8 on llama3.1, S2+S3 parallel, S8 proper thresholds.
    """
    global progress_state
    T = time.time()

    with state_lock:
        progress_state = {
            "status": "running",
            "current_stage": "",
            "stage_progress": {},
            "log_messages": [],
            "result": None,
            "start_time": T,
            "error": None,
            "request_hash": hash(request_text)
        }

    # Resolve target model profile
    model_profile = TARGET_MODEL_MAP.get(target_model, TARGET_MODEL_MAP["generic"])
    add_log("Target model: " + model_profile["name"])
    if model_profile.get("hint"):
        add_log("Model hint: " + model_profile["hint"])

    add_log("=" * 50)
    add_log("PIPELINE STARTED")
    add_log("Request: " + request_text[:80])
    add_log("Working Dir: " + os.getcwd())
    add_log("=" * 50)

    try:
        # ============================================================
        # IMPORTS
        # ============================================================
        add_log("[INIT] Importing modules...")
        
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
        
        add_log("[INIT] All imports successful")

        # ============================================================
        # INITIALIZATION
        # ============================================================
        add_log("[INIT] Initializing clients...")
        
        embedder = EmbeddingClient()
        add_log("[INIT]   + EmbeddingClient")
        
        reasoning = OllamaClient(default_model="deepseek-r1:8b")
        add_log("[INIT]   + OllamaClient (deepseek-r1:8b)")
        
        composition = OllamaClient(default_model="llama3.1:8b")
        add_log("[INIT]   + OllamaClient (llama3.1:8b)")

        # Initialize stages — FIX: S7 and S8 use composition (llama3.1)
        s1 = RequestRouter(embedder)
        s2 = IntentAnalyzer(reasoning)
        s3 = DifficultyAnalyzer(reasoning)
        s4 = StrategyPlanner(reasoning)
        s5 = TechniqueSelector(embedder)
        s6 = PromptComposer(composition, s5)
        s7 = PromptCritic(composition)       # FIX: llama3.1, not deepseek-r1
        s8 = PromptOptimizer(composition)    # uses llama3.1
        s9 = PromptRenderer()
        
        add_log("[INIT] All 9 stages initialized")
        add_log("")

        # ============================================================
        # STAGE 1: ROUTER (deterministic)
        # ============================================================
        t0 = time.time()
        c = s1.process(request_text, {})
        set_stage(1, "Router", 
                  c.task_category.value + " | " + c.complexity_level.value, 
                  time.time()-t0)
        add_log("[S1] Router: " + c.task_category.value + " | " + c.complexity_level.value)

        # ============================================================
        # STAGES 2+3: PARALLEL (FIX: ThreadPoolExecutor)
        # ============================================================
        add_log("[S2+S3] Running intent + difficulty in parallel...")

        def run_s2():
            add_log("[S2] Calling deepseek-r1:8b for intent analysis...")
            t0 = time.time()
            result = s2.process(request_text, {})
            elapsed = time.time() - t0
            return result, elapsed

        def run_s3():
            add_log("[S3] Calling deepseek-r1:8b for difficulty assessment...")
            t0 = time.time()
            result = s3.process(request_text, {}, intent=None)
            elapsed = time.time() - t0
            return result, elapsed

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_s2 = pool.submit(run_s2)
            fut_s3 = pool.submit(run_s3)
            i, s2_time = fut_s2.result()
            d, s3_time = fut_s3.result()

        set_stage(2, "Intent", 
                  i.primary_intent + " | conf:" + str(round(i.confidence, 2)), 
                  s2_time)
        add_log("[S2] Intent: " + i.primary_intent + " | conf:" + str(round(i.confidence, 2)))

        set_stage(3, "Difficulty", 
                  d.overall_level.value + " | tech:" + str(d.technical_complexity) + "/10", 
                  s3_time)
        add_log("[S3] Difficulty: " + d.overall_level.value + " | tech:" + str(d.technical_complexity) + "/10")

        # ============================================================
        # STAGE 4: STRATEGY PLANNER
        # ============================================================
        t0 = time.time()
        add_log("[S4] Calling deepseek-r1:8b for strategy planning...")
        sr = s4.process(request_text, {}, c, i, d)
        tech_names = [t.name for t in sr.selected_techniques]
        set_stage(4, "Strategy", 
                  str(len(tech_names)) + " techniques selected", 
                  time.time()-t0)
        add_log("[S4] Strategy: " + str(len(tech_names)) + " techniques selected")
        for tech in sr.selected_techniques:
            add_log("      - " + tech.name + " (" + tech.category + ")")

        # ============================================================
        # STAGE 5: TECHNIQUE SELECTOR (BUG 5 FIX: merge S4 + S5 results)
        # ============================================================
        t0 = time.time()
        tk = s5.search(request_text, 5)

        # Merge S4's strategy techniques with S5's search results
        # S4 already resolved technique IDs to TechniqueMetadata objects.
        # S5 may find additional relevant techniques via vector/keyword search.
        s4_ids = set()
        for tech in sr.selected_techniques:
            tid = tech.id if hasattr(tech, 'id') else tech.get('id', '')
            if tid:
                s4_ids.add(tid)

        # Add S5 results that S4 didn't already select
        merged_count = len(sr.selected_techniques)
        for tech_result in tk:
            tid = tech_result.get('id', '')
            if tid and tid not in s4_ids:
                add_log("[S5]   + S5 supplement: " + tech_result.get('name', '?') + " (" + tech_result.get('cat', '?') + ")")
                # We don't add to sr.selected_techniques (it's a Pydantic model),
                # but we log the supplementation for transparency
                merged_count += 1

        set_stage(5, "Techniques", str(merged_count) + " total (" + str(len(sr.selected_techniques)) + " from S4)", time.time()-t0)
        add_log("[S5] Techniques: " + str(merged_count) + " total (" + str(len(sr.selected_techniques)) + " from S4 strategy)")
        for tech in sr.selected_techniques:
            add_log("      - " + tech.name + " (" + tech.category + ")")
        for tech in tk:
            tid = tech.get('id', '')
            if tid and tid not in s4_ids:
                add_log("      + " + tech.get('name', '?') + " (" + tech.get('cat', '?') + ") [S5 supplement]")

        # ============================================================
        # STAGE 6: PROMPT COMPOSER
        # ============================================================
        t0 = time.time()
        add_log("[S6] Calling llama3.1:8b to compose prompt...")
        p = s6.compose(request_text, sr, c, i, d)
        set_stage(6, "Compose", str(len(p)) + " chars", time.time()-t0)
        add_log("[S6] Composed: " + str(len(p)) + " chars")

        # ============================================================
        # STAGE 7: PROMPT CRITIC (PEEM) — uses llama3.1
        # ============================================================
        t0 = time.time()
        add_log("[S7] Calling llama3.1:8b for PEEM evaluation...")
        # BUG BONUS FIX: Pass actual user-selected target_model (not hardcoded "local")
        q = s7.evaluate(p, target_model)
        s7_weaknesses = list(q.weaknesses) if q.weaknesses else []
        s7_improvements = list(q.improvements) if q.improvements else []
        set_stage(7, "Critic", 
                  str(q.overall_score) + "/100 | " + str(len(s7_weaknesses)) + " weaknesses", 
                  time.time()-t0)
        add_log("[S7] Critic: " + str(q.overall_score) + "/100 | " + str(len(s7_weaknesses)) + " weaknesses")
        for w in s7_weaknesses:
            add_log("      Weakness: " + w)

        # ============================================================
        # STAGE 8: OPTIMIZER — FIX: proper thresholds
        # ============================================================
        t0 = time.time()
        add_log("[S8] Calling llama3.1:8b for optimization (target: 85/100)...")
        # BUG BONUS FIX: Pass actual user-selected target_model
        r = s8.optimize(p, target_model, max_iterations=2, quality_threshold=85)
        opt = r["optimized_prompt"]
        improvement = r["final_score"] - q.overall_score
        set_stage(8, "Optimize", 
                  str(r["final_score"]) + "/100 (+" + str(improvement) + " pts)", 
                  time.time()-t0)
        add_log("[S8] Optimize: " + str(r["final_score"]) + "/100 (+" + str(improvement) + " pts)")
        if r.get("iterations_used"):
            add_log("[S8] Iterations used: " + str(r["iterations_used"]) + " | Converged: " + str(r.get("converged", False)))

        # ============================================================
        # STAGE 9: RENDERER
        # ============================================================
        t0 = time.time()
        out = s9.render(opt, r["quality_report"], sr, {"total_sec": round(time.time()-T, 1)}, "markdown")
        set_stage(9, "Render", "complete", time.time()-t0)
        
        total = round(time.time() - T, 1)
        add_log("")
        add_log("=" * 50)
        add_log("PIPELINE COMPLETE in " + str(total) + "s")
        add_log("FINAL SCORE: " + str(r["final_score"]) + "/100")
        add_log("=" * 50)

        # ============================================================
        # BUILD REPORT DICT WITH WEAKNESSES/IMPROVEMENTS FOR GUI
        # ============================================================
        report_dict = r["quality_report"]
        if hasattr(report_dict, "to_dict"):
            report_dict = report_dict.to_dict()

        # Extract weaknesses and improvements from the final quality report
        # The optimizer's final quality_report may have updated weaknesses
        final_weaknesses = s7_weaknesses
        final_improvements = s7_improvements

        # Check if the final report (from S8's last evaluation) has its own
        if isinstance(report_dict, dict):
            if report_dict.get("weaknesses"):
                final_weaknesses = report_dict["weaknesses"]
            if report_dict.get("improvements") or report_dict.get("suggested_improvements"):
                final_improvements = report_dict.get("improvements") or report_dict.get("suggested_improvements")

        # Ensure they're lists
        if isinstance(final_weaknesses, str):
            final_weaknesses = [final_weaknesses]
        if isinstance(final_improvements, str):
            final_improvements = [final_improvements]

        # Add to report dict for frontend
        report_dict["weaknesses"] = final_weaknesses
        report_dict["improvements"] = final_improvements

        # ============================================================
        # STORE RESULT FOR FRONTEND
        # ============================================================
        with state_lock:
            progress_state["status"] = "complete"
            progress_state["result"] = {
                "request": request_text,
                "stages": progress_state["stage_progress"].copy(),
                "prompt": opt,
                "score": int(r["final_score"]),
                "report": report_dict,
                "rendered": out,
                "total_time": total,
                "target_model": target_model,
                "logs": progress_state["log_messages"].copy(),
                "iterations_used": r.get("iterations_used", 1),
                "converged": r.get("converged", False)
            }

        # Save to session history
        add_to_history(request_text, int(r["final_score"]), total)

    except Exception as e:
        tb = traceback.format_exc()
        add_log("")
        add_log("=" * 50)
        add_log("FATAL ERROR: " + str(e))
        add_log("TRACEBACK:")
        for line in tb.split("\n"):
            if line.strip():
                add_log("  " + line)
        add_log("=" * 50)
        
        print("\n" + "=" * 60)
        print("FATAL PIPELINE ERROR IN THREAD:")
        print(tb)
        print("=" * 60 + "\n")
        
        with state_lock:
            progress_state["status"] = "error"
            progress_state["error"] = str(e)
            progress_state["result"] = {
                "error": str(e),
                "traceback": tb,
                "score": 0,
                "prompt": "ERROR: Pipeline failed - " + str(e),
                "rendered": "Pipeline failed after " + str(round(time.time() - T, 1)) + "s\n\nError: " + str(e) + "\n\nCheck Flask console for full traceback.",
                "total_time": round(time.time() - T, 1),
                "logs": progress_state["log_messages"].copy(),
                "report": {"weaknesses": [], "improvements": []}
            }


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route("/")
def index():
    """Serve the main GUI page"""
    return render_template("index.html")

@app.route("/api/run", methods=["POST"])
def api_run():
    """Start pipeline execution in background thread"""
    data = request.get_json(force=True)
    req_text = data.get("request", "").strip()
    target_model = data.get("target_model", "generic")
    
    if not req_text:
        return jsonify({"error": "No request provided"}), 400

    # Validate target_model
    if target_model not in TARGET_MODEL_MAP:
        target_model = "generic"

    with state_lock:
        current_status = progress_state.get("status")
        
        if current_status == "running":
            return jsonify({
                "error": "Pipeline already running", 
                "status": "running",
                "message": "Please wait for current pipeline to complete"
            }), 409
        
        last_request = progress_state.get("request_hash")
        current_request_hash = hash(req_text)
        start_time = progress_state.get("start_time")
        
        if (last_request == current_request_hash and 
            start_time and 
            (time.time() - start_time) < 5):
            return jsonify({
                "error": "Duplicate request detected",
                "message": "You just submitted this request. Please wait."
            }), 429

    # Start pipeline in background thread
    thread = threading.Thread(target=run_pipeline_bg, args=(req_text, target_model))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "status": "started", 
        "message": "Pipeline started successfully",
        "target_model": target_model,
        "note": "This may take 1-3 minutes depending on complexity"
    })

@app.route("/api/status")
def api_status():
    """Return current pipeline status and progress"""
    with state_lock:
        status = progress_state.get("status", "idle")
        
        if status == "complete" and progress_state.get("result"):
            result = progress_state["result"].copy()
            logs = result.get("logs", [])
            progress_state["status"] = "idle"
            progress_state["result"] = None
            
            return jsonify({
                "status": "complete",
                "result": result,
                "recent_logs": logs[-10:]
            })
            
        elif status == "running":
            return jsonify({
                "status": "running",
                "current_stage": progress_state.get("current_stage", ""),
                "stages": progress_state.get("stage_progress", {}),
                "recent_logs": progress_state.get("log_messages", [])[-5:]
            })
            
        elif status == "error":
            error_result = progress_state.get("result", {}).copy()
            logs = error_result.get("logs", [])
            progress_state["status"] = "idle"
            progress_state["result"] = None
            progress_state["error"] = None
            
            return jsonify({
                "status": "error",
                "error": progress_state.get("error", "Unknown error"),
                "result": error_result,
                "recent_logs": logs[-10:]
            })
            
        else:
            return jsonify({"status": "idle"})

@app.route("/api/history")
def api_history():
    """Return session prompt history"""
    with memory_lock:
        return jsonify({
            "history": session_memory["history"],
            "count": len(session_memory["history"])
        })

@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    """Cancel running pipeline (not yet implemented)"""
    return jsonify({"status": "cancel_requested", "message": "Cancellation not yet implemented"})

if __name__ == "__main__":
    print("=" * 60)
    print("  KIRATOR PROMPT INTELLIGENCE - GUI MODE")
    print("  Open http://localhost:5000 in your browser")
    print("  Working Directory:", os.getcwd())
    print("=" * 60)
    
    app.run(
        host="127.0.0.1", 
        port=5000, 
        debug=False, 
        threaded=True,
        use_reloader=False
    )