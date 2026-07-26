"""Delegate real coding work to Claude Code — 'Jarvis, add dark mode to my
portfolio' → Jarvis dispatches the Claude Code CLI on that project and reports
back. Jarvis doesn't need to be a senior engineer; he DRIVES one.

GATED (user must confirm the task aloud) and runs through the abortable
background-action path like installs — 'stop'/'abort' kills it mid-run.
"""
import os
import shutil

from brain import gate, tool
from tools.projects import _sections
from tools.system_admin import _run_abortable


def _find_claude() -> str | None:
    import glob
    cands = [shutil.which("claude"),
             os.path.expanduser("~/.claude/local/claude"),
             os.path.expanduser("~/.local/bin/claude"),
             "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]
    # nvm installs to ~/.nvm/versions/node/<ver>/bin — not on the daemon's PATH.
    cands += sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/claude")),
                    reverse=True)
    for cand in cands:
        if cand and os.path.exists(cand):
            return cand
    return None


def _norm(s: str) -> str:
    return s.lower().replace("-", " ").replace("_", " ").strip()


def _project_path(name: str) -> str | None:
    low = _norm(name)
    for n, body in _sections().items():
        if low in _norm(n) or _norm(n) in low:
            for line in body.splitlines():
                if "**Path:**" in line:
                    p = line.split("**Path:**")[1].strip().split("(")[0].strip()
                    p = os.path.expanduser(p)
                    for cand in (p, p.replace("'", "’")):  # curly-apostrophe dirs
                        if os.path.isdir(cand):
                            return cand
    return None


@tool({"name": "delegate_coding",
       "description": "Hand a coding task to Claude Code (a full coding agent) on one of "
                      "the user's projects — write features, fix bugs, refactor. Gated: "
                      "the user confirms before it runs; can be aborted with 'stop'.",
       "parameters": {"type": "object",
           "properties": {
               "project": {"type": "string",
                           "description": "which project, e.g. 'portfolio', 'job-copilot'"},
               "task": {"type": "string",
                        "description": "clear instruction of what to build/fix"}},
           "required": ["project", "task"]}})
def delegate_coding(project: str, task: str):
    binary = _find_claude()
    if not binary:
        return {"error": "Claude Code CLI not installed. One-time setup: "
                         "npm install -g @anthropic-ai/claude-code  (then it works by voice)"}
    path = _project_path(project)
    if not path:
        return {"error": f"couldn't resolve a project folder for '{project}'",
                "known": list(_sections())}
    code, out, err = _run_abortable(
        [binary, "-p", task, "--permission-mode", "acceptEdits"],
        shell=False, timeout=900, label=f"coding task on {project}", cwd=path,
    )
    return {"project": project, "cwd": path, "exit": code,
            "report": (out or "").strip()[-1200:] or (err or "").strip()[-300:]}


gate("delegate_coding")   # never dispatches without a spoken yes
