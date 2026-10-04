"""
Per-install Flask secret key.

The old build used one shared key for every install.
This module creates a random key the first time the app runs and stores it
under the user data folder (normally ~/.kirator/prompt_intelligence/secret_key).

The file stays on that computer. It is not part of the git repo.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

_MIN_LENGTH = 32


def load_or_create_secret_key(path: Path) -> str:
    """Return the saved key, or create a new random one and save it."""
    path = Path(path)
    existing = _read_key(path)
    if existing:
        return existing

    key = secrets.token_hex(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write via a temp file so a crash cannot leave a half-written key.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        # Windows may refuse chmod. The key is still only on this machine.
        pass
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _read_key(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if len(key) < _MIN_LENGTH:
        return None
    return key
