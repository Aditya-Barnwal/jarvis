"""Apple Reminders + Notes — synced with the iPhone via iCloud, driven by
AppleScript. First use triggers a one-time macOS Automation permission prompt;
until granted, these return a clear error instead of hanging (timeouts on every
call). Text is sanitized before being embedded in AppleScript."""
import subprocess
from datetime import datetime, timedelta

from brain import tool


def _osa(script: str, timeout: int = 10) -> tuple[bool, str]:
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            err = r.stderr.strip()
            if "authoriz" in err.lower() or "-1743" in err:
                return False, ("needs permission: System Settings → Privacy → "
                               "Automation → allow control of this app")
            return False, err[:120]
        return True, r.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "timed out — likely waiting on a permission prompt"


def _q(text: str) -> str:
    """Escape for embedding in an AppleScript double-quoted string."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


@tool({"name": "add_reminder",
       "description": "Add a reminder (Apple Reminders — appears on the iPhone too). "
                      "Optional due in N hours from now.",
       "parameters": {"type": "object",
           "properties": {"text": {"type": "string"},
                          "hours_from_now": {"type": "number"}},
           "required": ["text"]}})
def add_reminder(text: str, hours_from_now: float = 0):
    if hours_from_now:
        due = datetime.now() + timedelta(hours=hours_from_now)
        due_s = due.strftime("%d/%m/%Y %H:%M")
        script = (f'tell application "Reminders" to make new reminder with properties '
                  f'{{name:"{_q(text)}", due date:date "{due_s}"}}')
    else:
        script = (f'tell application "Reminders" to make new reminder with properties '
                  f'{{name:"{_q(text)}"}}')
    ok, out = _osa(script)
    return {"added": text, "due_in_hours": hours_from_now or None} if ok else {"error": out}


@tool({"name": "list_reminders",
       "description": "List open (incomplete) reminders.",
       "parameters": {"type": "object", "properties": {}}})
def list_reminders():
    # Scoped to the default list: 2.7s vs ~30s for the all-lists query.
    ok, out = _osa('tell application "Reminders" to get name of every reminder '
                   'of default list whose completed is false', timeout=15)
    if not ok:
        return {"error": out}
    items = [x.strip() for x in out.split(",") if x.strip()]
    return {"reminders": items[:20], "count": len(items)}


@tool({"name": "create_note",
       "description": "Create a note in Apple Notes (syncs to the iPhone).",
       "parameters": {"type": "object",
           "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
           "required": ["title", "body"]}})
def create_note(title: str, body: str):
    script = (f'tell application "Notes" to make new note at folder "Notes" with '
              f'properties {{name:"{_q(title)}", body:"{_q(body)}"}}')
    ok, out = _osa(script)
    return {"created": title} if ok else {"error": out}


@tool({"name": "search_notes",
       "description": "Search Apple Notes by title/content; returns matching note titles.",
       "parameters": {"type": "object",
           "properties": {"query": {"type": "string"}}, "required": ["query"]}})
def search_notes(query: str):
    script = (f'''tell application "Notes"
        set hits to {{}}
        repeat with n in notes
            if (name of n contains "{_q(query)}") or (plaintext of n contains "{_q(query)}") then
                copy (name of n) to end of hits
            end if
        end repeat
        return hits
    end tell''')
    ok, out = _osa(script, timeout=20)
    if not ok:
        return {"error": out}
    return {"matches": [x.strip() for x in out.split(",") if x.strip()][:10]}
