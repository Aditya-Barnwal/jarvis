"""The user's projects — Jarvis's knowledge of everything on this laptop, so he
can answer about them and work on them. Deep detail lives in
data/knowledge/projects.md (kept out of every prompt); these tools recall it
on demand. Update the knowledge file as projects evolve."""
import difflib
import os
import re

from brain import tool

_KB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                   "data", "knowledge", "projects.md")


def _sections() -> dict[str, str]:
    try:
        text = open(_KB).read()
    except OSError:
        return {}
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    out = {}
    for p in parts:
        name, _, body = p.partition("\n")
        out[name.strip()] = body.strip()
    return out


@tool({"name": "list_projects",
       "description": "List all of the user's projects on this laptop (name + one-liner).",
       "parameters": {"type": "object", "properties": {}}})
def list_projects():
    out = []
    for name, body in _sections().items():
        m = re.search(r"\*\*What:\*\*\s*(.+)", body)
        out.append({"project": name, "about": (m.group(1) if m else body[:80])[:120]})
    return {"projects": out}


@tool({"name": "project_info",
       "description": "Everything known about one of the user's projects (path, stack, "
                      "state, how to run). Fuzzy name match — 'job copilot', 'inventory', "
                      "'legal analyzer' all work.",
       "parameters": {"type": "object",
           "properties": {"name": {"type": "string"}}, "required": ["name"]}})
def project_info(name: str):
    secs = _sections()
    if not secs:
        return {"error": "knowledge base missing (data/knowledge/projects.md)"}
    low = name.strip().lower()
    for n in secs:                                   # substring match first
        if low in n.lower() or n.lower() in low:
            return {"project": n, "info": secs[n]}
    close = difflib.get_close_matches(low, [n.lower() for n in secs], n=1, cutoff=0.4)
    if close:
        n = next(k for k in secs if k.lower() == close[0])
        return {"project": n, "info": secs[n]}
    return {"error": f"no project matching '{name}'",
            "available": list(secs)}
