"""
Pick a port for the local GUI.

Port 5000 is a poor default: macOS AirPlay Receiver uses it, and lots of
other dev servers do too. Prompt Intelligence prefers 5070 (see
config/settings.yaml). If that port is already taken, we try the next
ones instead of killing whatever is listening.
"""

from __future__ import annotations

import socket


def choose_listen_port(host: str, preferred: int, span: int = 20) -> int:
    """
    Return `preferred` when it is free, otherwise the next free port.

    Checks up to `span` ports (5070, 5071, ... ). Raises RuntimeError if
    every one of them is busy.
    """
    if preferred < 1 or preferred > 65535:
        raise ValueError(f"Port must be between 1 and 65535, got {preferred}")

    last = min(65535, preferred + span - 1)
    for port in range(preferred, last + 1):
        if _port_is_free(host, port):
            return port
    raise RuntimeError(
        f"No free port from {preferred} to {last} on {host}. "
        "Close another program or set server.port in config/settings.yaml."
    )


def _port_is_free(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except OSError:
        return False
    finally:
        sock.close()
    return True
