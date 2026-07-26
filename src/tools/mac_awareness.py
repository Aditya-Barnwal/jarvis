"""Device awareness — Jarvis runs ON your Mac, so it can read what's happening
here (unlike a cloud assistant). Uses AppleScript/shell; first use prompts for
Automation permission. Each reads real state — no fabrication.
"""
import subprocess

from brain import tool


def _osa(script: str) -> str:
    return subprocess.run(["osascript", "-e", script],
                          capture_output=True, text=True).stdout.strip()


@tool({"name": "get_active_app",
       "description": "Which application is in the foreground / being used right now.",
       "parameters": {"type": "object", "properties": {}}})
def get_active_app():
    app = _osa('tell application "System Events" to get name of first process '
               'whose frontmost is true')
    return {"active_app": app or None}


@tool({"name": "get_open_apps",
       "description": "List the apps currently open (visible, not background).",
       "parameters": {"type": "object", "properties": {}}})
def get_open_apps():
    out = _osa('tell application "System Events" to get name of every process '
               'whose background only is false')
    return {"apps": [a.strip() for a in out.split(",") if a.strip()]}


@tool({"name": "get_now_playing",
       "description": "What music is currently playing (Spotify or Apple Music), if any.",
       "parameters": {"type": "object", "properties": {}}})
def get_now_playing():
    for app in ("Spotify", "Music"):
        running = _osa(f'tell application "System Events" to (name of processes) contains "{app}"')
        if running != "true":
            continue
        state = _osa(f'tell application "{app}" to player state as string')
        if state == "playing":
            track = _osa(f'tell application "{app}" to return '
                         f'(name of current track) & " — " & (artist of current track)')
            return {"app": app, "track": track}
    return {"playing": False}


@tool({"name": "read_clipboard",
       "description": "Read what's currently on the clipboard (copied text).",
       "parameters": {"type": "object", "properties": {}}})
def read_clipboard():
    txt = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    return {"clipboard": txt[:500]}
