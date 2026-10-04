"""Flask API integration tests (no live Ollama required for most cases)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.api, pytest.mark.overnight]


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "version" in data


def test_index_serves_branded_gui(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Kirator" in html
    assert "Improve Prompt" in html
    assert "brand-mark" in html
    assert "design-tokens.css" in html
    # Built-in mark, a shipped PNG, or the optional brand kit. A PNG is not required.
    assert "/static/mark.svg" in html or "/static/logo.png" in html or "/brand/logo" in html


def test_builtin_mark_does_not_need_a_logo_png(client):
    """The GUI theme must load when no logo PNG is installed."""
    resp = client.get("/static/mark.svg")
    assert resp.status_code == 200
    assert b"<svg" in resp.data
    # logo.png is optional. Missing it must not be a test failure.
    png = client.get("/static/logo.png")
    assert png.status_code in (200, 404)


def test_targets_endpoint(client):
    resp = client.get("/api/targets")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["targets"]) >= 5
    ids = {t["id"] for t in data["targets"]}
    assert "chatgpt" in ids
    assert "claude" in ids


def test_plugins_endpoint(client):
    resp = client.get("/api/plugins")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] >= 1
    assert any(p["id"] == "critic_hallucination_risk" for p in data["plugins"])


def test_history_empty_then_clear(client):
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 0

    resp = client.delete("/api/history")
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 0


def test_events_stream_when_idle(client):
    """The live stage stream answers immediately when nothing is running."""
    resp = client.get("/api/events")
    assert resp.status_code == 200
    assert "text/event-stream" in (resp.content_type or "")
    body = resp.get_data(as_text=True)
    assert "data:" in body
    assert "idle" in body


def test_run_rejects_empty(client):
    resp = client.post("/api/run", json={"request": "   ", "target_model": "generic"})
    assert resp.status_code == 400
    resp = client.post("/api/run", json={"request": "   ", "target_model": "generic"})
    assert resp.status_code == 400


def test_run_starts_and_cancel(client, flask_app):
    """Start a fake long pipeline and verify cancel API works."""
    from src.core.exceptions import PipelineCancelled

    def fake_run(self, request_text, target_model):
        self.add_log("FAKE START")
        self.set_stage(1, "Router", "fake", 0.1)
        try:
            for _ in range(50):
                self._check_cancel()
                time.sleep(0.05)
        except PipelineCancelled:
            self.add_log("FAKE CANCELLED")
            with self._lock:
                self._state["status"] = "cancelled"
                self._state["cancelled"] = True
                self._state["error"] = "Cancelled by user"
                self._state["result"] = {
                    "error": "Cancelled by user",
                    "rendered": "cancelled",
                    "score": 0,
                    "report": {},
                    "total_time": 0.1,
                    "logs": [],
                    "stages": {},
                }
            return
        with self._lock:
            self._state["status"] = "complete"
            self._state["result"] = {"score": 1, "prompt": "x", "rendered": "x", "report": {}, "total_time": 0.1, "logs": [], "stages": {}}

    from src.gui import app as gui_mod

    with patch.object(type(gui_mod.pipeline), "_run", fake_run):
        resp = client.post(
            "/api/run",
            json={"request": "automated cancel probe", "target_model": "claude"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "started"

        status = client.get("/api/status").get_json()
        assert status["status"] in ("running", "cancelled", "complete", "idle")

        cancel = client.post("/api/cancel")
        assert cancel.status_code == 200
        assert cancel.get_json()["status"] in ("cancel_requested", "idle")

        deadline = time.time() + 5
        while time.time() < deadline:
            payload = client.get("/api/status").get_json()
            if payload["status"] in ("cancelled", "complete", "error", "idle"):
                break
            time.sleep(0.1)
