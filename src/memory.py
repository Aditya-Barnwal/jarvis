"""Phase 2 — Memory. Local SQLite store: facts, preferences, key/value settings.

Two roles:
  1. Persistence for live settings (assistant_name, voice_ref) so voice-command
     changes survive restarts.
  2. Durable facts/preferences about the user, injected into every brain call
     via build_context() so Jarvis "knows" you instead of resetting each session.

All local, all private — the DB lives under data/ (git-ignored). ChromaDB /
semantic recall is a later upgrade (see docs/phases/phase-2-memory.md).
"""
import os
import sqlite3
from datetime import datetime, timezone

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.db")
_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH)
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS facts ("
            "key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
        )
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS learned ("
            "id INTEGER PRIMARY KEY, fact TEXT, topic TEXT, source TEXT, ts TEXT)"
        )
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS exchanges ("
            "id INTEGER PRIMARY KEY, ts TEXT, user TEXT, assistant TEXT)"
        )
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions ("
            "id INTEGER PRIMARY KEY, ts TEXT, summary TEXT)"
        )
        _conn.commit()
    return _conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def remember(key: str, value: str) -> None:
    """Store/overwrite a durable fact or setting (correction = overwrite)."""
    db = _db()
    db.execute(
        "INSERT INTO facts(key, value, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, str(value), _now()),
    )
    db.commit()


def recall(key: str, default: str | None = None) -> str | None:
    row = _db().execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def forget(key: str) -> None:
    db = _db()
    db.execute("DELETE FROM facts WHERE key=?", (key,))
    db.commit()


def all_facts() -> dict[str, str]:
    return dict(_db().execute("SELECT key, value FROM facts").fetchall())


# --- Learned facts (explicit teaching + passive extraction) ---------------
def remember_fact(fact: str, topic: str = "general", source: str = "user") -> int:
    """Store a durable free-text fact. Dedupes: an (almost) identical fact updates
    the existing row instead of piling up copies that bloat every future prompt."""
    import difflib

    fact = fact.strip()
    db = _db()
    for fid, existing in db.execute(
            "SELECT id, fact FROM learned ORDER BY id DESC LIMIT 100").fetchall():
        if existing.lower() == fact.lower() or \
                difflib.SequenceMatcher(None, existing.lower(), fact.lower()).ratio() > 0.9:
            db.execute("UPDATE learned SET fact=?, topic=?, source=?, ts=? WHERE id=?",
                       (fact, topic, source, _now(), fid))
            db.commit()
            return fid
    cur = db.execute(
        "INSERT INTO learned(fact, topic, source, ts) VALUES(?,?,?,?)",
        (fact, topic, source, _now()),
    )
    db.commit()
    return cur.lastrowid


def learned_facts(limit: int = 50) -> list[str]:
    rows = _db().execute(
        "SELECT fact FROM learned ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [r[0] for r in rows]


# --- Cross-session conversation memory ------------------------------------
def log_exchange(user: str, assistant: str) -> None:
    """Persist every exchange so conversations survive restarts. Keeps the last
    500 rows (raw log); long-term recall happens via session summaries."""
    db = _db()
    db.execute("INSERT INTO exchanges(ts, user, assistant) VALUES(?,?,?)",
               (_now(), user[:500], assistant[:500]))
    db.execute("DELETE FROM exchanges WHERE id NOT IN "
               "(SELECT id FROM exchanges ORDER BY id DESC LIMIT 500)")
    db.commit()


def save_session_summary(summary: str) -> None:
    if summary and summary.strip():
        db = _db()
        db.execute("INSERT INTO sessions(ts, summary) VALUES(?,?)", (_now(), summary.strip()))
        db.commit()
        _consolidate_sessions()


def _consolidate_sessions(keep_recent: int = 8, threshold: int = 16) -> None:
    """Long-term memory hygiene: when session summaries pile up past `threshold`,
    compress everything but the most recent `keep_recent` into ONE digest line —
    old context stays available without bloating every prompt forever."""
    db = _db()
    rows = db.execute("SELECT id, ts, summary FROM sessions ORDER BY id").fetchall()
    if len(rows) < threshold:
        return
    old, recent = rows[:-keep_recent], rows[-keep_recent:]
    try:
        import brain
        if brain.use_groq():
            text = "\n".join(f"[{ts[:10]}] {s}" for _, ts, s in old)
            digest = brain.ask("Merge these conversation summaries into ONE dense "
                               "summary of at most 3 sentences, keeping concrete "
                               "durable facts and dropping trivia:\n" + text)
        else:   # offline: cheap truncation, don't load the 7B for housekeeping
            digest = " | ".join(s[:60] for _, _, s in old[-5:])
        db.execute("DELETE FROM sessions WHERE id <= ?", (old[-1][0],))
        # reuse the freed id so the digest sorts BEFORE the recent summaries
        db.execute("INSERT INTO sessions(id, ts, summary) VALUES(?,?,?)",
                   (old[-1][0], old[-1][1],
                    "[older conversations, condensed] " + digest.strip()))
        db.commit()
    except Exception:
        pass   # housekeeping must never break a session


def recent_summaries(n: int = 3) -> list[tuple[str, str]]:
    rows = _db().execute(
        "SELECT ts, summary FROM sessions ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return list(reversed(rows))


def build_context() -> str:
    """Render memory as context for every brain call: durable facts + what the
    last few conversations were about — so Jarvis remembers across sessions."""
    facts = learned_facts()
    kv = {k: v for k, v in all_facts().items() if k not in ("assistant_name", "voice_ref")}
    lines = [f"- {f}" for f in facts] + [f"- {k}: {v}" for k, v in kv.items()]
    out = []
    if lines:
        out.append("What you know about the user:\n" + "\n".join(lines))
    sums = recent_summaries()
    if sums:
        out.append("Recent conversations (oldest first):\n" +
                   "\n".join(f"- [{ts[:10]}] {s}" for ts, s in sums))
    return "\n\n".join(out)
