"""job-copilot integration (the Phase 6 vision + Aditya's directive: job applying
is now Jarvis's job). Read-only: status/matches from the local FastAPI service;
if it isn't running, says so and offers the (gated) way to start it."""
import json
import urllib.request

from brain import tool

BASE = "http://localhost:8000"


def _get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=4) as r:
        return json.load(r)


@tool({"name": "job_status",
       "description": "Job search status from job-copilot: top-scored open roles and "
                      "counts. Read-only; the service must be running locally.",
       "parameters": {"type": "object", "properties": {}}})
def job_status():
    try:
        jobs = _get("/api/jobs")
        items = jobs.get("jobs", jobs.get("items", [])) if isinstance(jobs, dict) else jobs
        top = []
        for j in (items or [])[:5]:
            if isinstance(j, dict):
                top.append({k: j.get(k) for k in ("company", "title", "score", "status")
                            if j.get(k) is not None})
        return {"total_roles": len(items or []), "top_matches": top}
    except Exception:
        return {"error": "job-copilot isn't running. Offer to start it: the command is "
                         "'cd ~/Downloads/files/job-copilot && "
                         "./.venv/bin/python -m uvicorn server.app:app --port 8000' "
                         "via run_command (gated)."}
