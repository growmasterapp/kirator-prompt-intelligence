"""
Run a blocking model call so Cancel can stop it.

Ollama's chat call waits until the model finishes. A cancel flag checked
only between stages would sit there for the whole call. This helper runs
the call on a side thread and watches the cancel flag every few tenths of
a second. When Cancel is pressed, it closes the HTTP client (so the call
unblocks) and raises PipelineCancelled.
"""

from __future__ import annotations

import threading
from typing import Callable

from src.core.exceptions import PipelineCancelled


def run_interruptible(fn: Callable, cancel_event: threading.Event | None, abort: Callable | None = None, poll_seconds: float = 0.15):
    """
    Call fn() and return its value.

    If cancel_event is set while fn is still running, call abort() and
    raise PipelineCancelled instead of waiting for fn to finish.
    """
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled("Cancelled before model call")

    box: dict = {}
    done = threading.Event()

    def _call() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = exc
        finally:
            done.set()

    worker = threading.Thread(target=_call, name="kirator-model-call", daemon=True)
    worker.start()

    while not done.wait(poll_seconds):
        if cancel_event is not None and cancel_event.is_set():
            if abort is not None:
                try:
                    abort()
                except Exception:
                    pass
            # Give the socket a moment to close, then stop waiting.
            done.wait(1.5)
            raise PipelineCancelled("Cancelled during model call")

    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled("Cancelled during model call")
    if "error" in box:
        raise box["error"]
    return box.get("value")
