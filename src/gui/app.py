"""
Kirator Prompt Intelligence — Flask GUI server.

Thin HTTP layer over PipelineService. Pipeline orchestration lives in
src/pipeline/service.py.
"""

from __future__ import annotations

import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure project root is on path (src/gui → project root = parents[2])
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from flask import Flask, jsonify, render_template, request

from src.core.config import get_settings
from src.core.history_store import HistoryStore
from src.core.logging_setup import setup_logging
from src.core.target_profiles import get_target_profile, list_target_profiles
from src.pipeline.service import get_pipeline_service

settings = get_settings()
setup_logging(log_dir=settings.user_data_dir / "logs")

_TEMPLATE_DIR = os.path.join(_SCRIPT_DIR, "templates")
_STATIC_DIR = os.path.join(_SCRIPT_DIR, "static")

app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)
app.config["SECRET_KEY"] = "kirator-gui-secret-v3"

pipeline = get_pipeline_service()
history = pipeline.history


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def api_health():
    return jsonify(
        {
            "status": "ok",
            "project": settings.project_name,
            "version": settings.project_version,
            "pipeline": "idle" if not pipeline.is_running() else "running",
        }
    )


@app.route("/api/targets")
def api_targets():
    return jsonify({"targets": list_target_profiles()})


@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(force=True) or {}
    req_text = (data.get("request") or "").strip()
    target_model = data.get("target_model", "generic")
    profile = get_target_profile(target_model)

    result = pipeline.start(req_text, profile.id)
    if not result.get("ok"):
        return jsonify(result), int(result.get("code", 400))
    return jsonify(result)


@app.route("/api/status")
def api_status():
    terminal = pipeline.consume_terminal()
    if terminal:
        return jsonify(terminal)
    snap = pipeline.snapshot()
    if snap["status"] == "running":
        return jsonify(
            {
                "status": "running",
                "current_stage": snap["current_stage"],
                "stages": snap["stages"],
                "recent_logs": snap["recent_logs"],
            }
        )
    return jsonify({"status": "idle"})


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    return jsonify(pipeline.cancel())


@app.route("/api/history", methods=["GET", "DELETE"])
def api_history():
    if request.method == "DELETE":
        history.clear()
        return jsonify({"history": [], "count": 0})
    items = history.list()
    return jsonify({"history": items, "count": len(items)})


@app.route("/api/plugins")
def api_plugins():
    plugins = pipeline.list_plugins()
    return jsonify({"plugins": plugins, "count": len(plugins)})


if __name__ == "__main__":
    print("=" * 60)
    print(f"  {settings.project_name}")
    print(f"  Open http://{settings.server.host}:{settings.server.port}")
    print("=" * 60)
    app.run(
        host=settings.server.host,
        port=settings.server.port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
