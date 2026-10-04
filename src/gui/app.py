"""
Kirator Prompt Intelligence — Flask GUI server.

Thin HTTP layer over PipelineService. Pipeline orchestration lives in
src/pipeline/service.py.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure project root is on path (src/gui → project root = parents[2])
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context

from src.core.config import get_settings
from src.core.history_store import HistoryStore
from src.core.logging_setup import setup_logging
from src.core.ports import choose_listen_port
from src.core.secret_store import load_or_create_secret_key
from src.core.target_profiles import get_target_profile, list_target_profiles
from src.gui.brand import brand_logo_file, brand_theme_file, logo_url, theme_url
from src.pipeline.service import get_pipeline_service

settings = get_settings()
setup_logging(log_dir=settings.user_data_dir / "logs")

_TEMPLATE_DIR = os.path.join(_SCRIPT_DIR, "templates")
_STATIC_DIR = os.path.join(_SCRIPT_DIR, "static")

app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)
# Random key for this install, stored outside the repo. Not the old shared string.
app.config["SECRET_KEY"] = load_or_create_secret_key(settings.user_data_dir / "secret_key")

pipeline = get_pipeline_service()
history = pipeline.history


@app.route("/")
def index():
    return render_template(
        "index.html",
        logo_url=logo_url(Path(_STATIC_DIR)),
        brand_theme=theme_url(),
    )


@app.route("/brand/logo")
def brand_logo():
    """Logo from the optional brand kit. 404 when the kit is not installed."""
    path = brand_logo_file()
    if path is None:
        return jsonify({"error": "Brand kit is not installed. Using the built-in mark."}), 404
    return send_file(path)


@app.route("/brand/theme.css")
def brand_theme():
    """Extra CSS from the optional brand kit. The built-in theme still loads."""
    path = brand_theme_file()
    if path is None:
        return jsonify({"error": "Brand kit is not installed. Using the built-in theme."}), 404
    return send_file(path, mimetype="text/css")


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


@app.route("/api/events")
def api_events():
    """
    Live stage updates for the page (Server-Sent Events).

    The GUI opens this when a run starts. Each event is a JSON snapshot:
    which stage is running, the log tail, and the final result when done.
    """

    def generate():
        last_serial = -1
        seen_running = False
        while True:
            snap = pipeline.snapshot()
            status = snap.get("status")
            if status == "running":
                seen_running = True
            serial = int(snap.get("serial", 0))
            if serial != last_serial:
                last_serial = serial
                yield "data: " + json.dumps(snap) + "\n\n"
            if status in ("complete", "error", "cancelled"):
                break
            # Nothing is running. Don't hold the connection open.
            if status == "idle" and not seen_running:
                break
            pipeline.wait_for_update(last_serial, timeout=12)
            yield ": ping\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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


def listen_address() -> tuple[str, int]:
    """
    Choose the address to bind.

    Prefers the port in settings (5070). If that port is busy, uses the
    next free one. Does not kill whatever is already listening.
    """
    host = settings.server.host
    preferred = int(settings.server.port)
    port = choose_listen_port(host, preferred)
    if port != preferred:
        print(f"  Port {preferred} is busy. Using http://{host}:{port} instead.")
    return host, port


if __name__ == "__main__":
    host, port = listen_address()
    print("=" * 60)
    print(f"  {settings.project_name}")
    print(f"  Open http://{host}:{port}")
    print("=" * 60)
    app.run(
        host=host,
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
