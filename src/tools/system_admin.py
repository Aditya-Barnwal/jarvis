"""Admin + coding tools — powerful, so install_app and run_command are GATED
(they don't run until you say yes) AND abortable mid-flight ("stop"/"abort"
while running kills the process). write_file is sandboxed to a workspace dir."""
import os
import signal
import subprocess

from brain import gate, tool

WORKSPACE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "workspace")

# The currently running gated process (install/command) — so it can be aborted.
_CURRENT = {"proc": None, "label": None}


def _run_abortable(cmd, shell: bool, timeout: int, label: str, cwd: str | None = None):
    """Run a subprocess in its own process group, registered for mid-flight abort."""
    os.makedirs(WORKSPACE, exist_ok=True)
    proc = subprocess.Popen(cmd, shell=shell, cwd=cwd or WORKSPACE, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    _CURRENT["proc"], _CURRENT["label"] = proc, label
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out or "", err or ""
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = proc.communicate()
        return -1, out or "", (err or "") + "\n[timed out]"
    finally:
        _CURRENT["proc"] = None


def abort_current() -> dict:
    """Kill the running gated action (whole process group). Called by the voice
    loop when the user says stop/abort while an install/command is running."""
    proc = _CURRENT["proc"]
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        return {"aborted": _CURRENT["label"] or "action"}
    return {"nothing_running": True}


def _safe_path(filename: str) -> str:
    path = os.path.normpath(os.path.join(WORKSPACE, filename))
    if not path.startswith(os.path.normpath(WORKSPACE) + os.sep):
        raise ValueError("path escapes the workspace")
    return path


@tool({"name": "install_app",
       "description": "Install a macOS app or CLI tool via Homebrew (e.g. 'visual-studio-code', "
                      "'vlc', 'wget'). Gated: asks the user to confirm first.",
       "parameters": {"type": "object",
           "properties": {"name": {"type": "string", "description": "Homebrew cask/formula name"}},
           "required": ["name"]}})
def install_app(name: str):
    code, out, err = _run_abortable(["brew", "install", "--cask", name],
                                    shell=False, timeout=900, label=f"install {name}")
    if code != 0 and "aborted" not in err.lower():   # not a cask? try a formula
        code, out, err = _run_abortable(["brew", "install", name],
                                        shell=False, timeout=900, label=f"install {name}")
    ok = code == 0
    return {"installed": name if ok else None, "ok": ok,
            "output": (out + err).strip()[-300:]}


@tool({"name": "write_file",
       "description": "Write text/code to a file in Jarvis's workspace folder. Use for creating "
                      "scripts and code. Returns the path (open it in an editor to view).",
       "parameters": {"type": "object",
           "properties": {"filename": {"type": "string"}, "content": {"type": "string"}},
           "required": ["filename", "content"]}})
def write_file(filename: str, content: str):
    os.makedirs(WORKSPACE, exist_ok=True)
    path = _safe_path(filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return {"wrote": path, "bytes": len(content)}


@tool({"name": "run_command",
       "description": "Run a shell command in the workspace (e.g. run a script, run tests, git). "
                      "Use to execute or debug code. Gated: asks the user to confirm first.",
       "parameters": {"type": "object",
           "properties": {"command": {"type": "string"}}, "required": ["command"]}})
def run_command(command: str):
    code, out, err = _run_abortable(command, shell=True, timeout=120,
                                    label=f"command: {command[:60]}")
    return {"exit_code": code, "stdout": out[-1500:], "stderr": err[-600:]}


gate("install_app", "run_command")   # these two require confirmation
