"""Is the machine online? Used to route the brain (Groq vs Ollama).

A single socket probe with a short timeout, cached for 30s so we don't pay a
TCP connect on every single turn (the daemon calls this constantly).
"""
import socket
import time

_CACHE_TTL = 30.0
_last: tuple[float, bool] | None = None   # (checked_at, result)


def is_online(host: str = "api.groq.com", port: int = 443, timeout: float = 1.5) -> bool:
    """True if we can reach Groq. False means fall back to local Ollama."""
    global _last
    now = time.time()
    if _last and now - _last[0] < _CACHE_TTL:
        return _last[1]
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        result = True
    except OSError:
        result = False
    _last = (now, result)
    return result
