# Capability: Notes

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "Take a note", "what did I note about the landlord?", "add this to my grocery list" — including notes you made on your iPhone.

**Reality:** ✅ clean and local. Apple Notes syncs from your iPhone to your Mac via iCloud, and the Mac's Notes.app is fully scriptable via AppleScript. Jarvis reads and writes; changes sync back to your phone.

---

## How it works

Notes you write on your iPhone appear in Notes.app on the Mac (same Apple ID, iCloud Notes on). AppleScript can create, read, and search them. Because it's the local Notes.app being driven, this works **offline** too — it just reads whatever last synced.

```python
# src/tools/notes.py
import subprocess
from brain import tool

def _osa(script: str) -> str:
    return subprocess.run(["osascript", "-e", script],
                          capture_output=True, text=True).stdout.strip()

@tool({"name": "create_note",
       "description": "Create a new note in Apple Notes.",
       "parameters": {"type": "object",
           "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
           "required": ["title", "body"]}})
def create_note(title: str, body: str):
    _osa(f'''tell application "Notes"
        make new note at folder "Notes" with properties {{name:"{title}", body:"{body}"}}
    end tell''')
    return {"created": title}

@tool({"name": "search_notes",
       "description": "Find notes whose title or body contains the query text.",
       "parameters": {"type": "object",
           "properties": {"query": {"type": "string"}},
           "required": ["query"]}})
def search_notes(query: str):
    out = _osa(f'''tell application "Notes"
        set hits to {{}}
        repeat with n in notes
            if (name of n contains "{query}") or (body of n contains "{query}") then
                copy (name of n) to end of hits
            end if
        end repeat
        return hits
    end tell''')
    return {"matches": out}
```

## What Jarvis can do

- **Capture** — "note that the plumber comes Tuesday" → new note, synced to your phone within seconds.
- **Append** — "add milk to my grocery list" → finds the note, appends a line.
- **Recall** — "what did I note about the landlord?" → searches bodies, reads it back.
- **Dictate long-form** — speak a paragraph, Jarvis writes it as a note (grammar-checked first if you want — see [grammar.md](grammar.md)).

## Constraints & honesty

- **iCloud Notes must be on** for iPhone notes to reach the Mac. If it's off, Jarvis only sees Mac-local notes.
- AppleScript's Notes support is a little clunky with rich formatting (checklists, images). Plain-text notes are reliable; complex formatting is hit-or-miss — keep Jarvis-created notes simple.
- First use triggers a macOS **Automation permission** prompt for controlling Notes.app. One-time grant.
- Body text with quotes/special characters needs escaping (the real implementation sanitizes input before building the AppleScript).

## Example

```
You: "Jarvis, note that Anjali's flight lands Saturday 7pm, terminal 2."
Jarvis: "Saved a note 'Anjali flight' — Saturday 7pm, terminal 2. It'll be on your
         phone too."
```
