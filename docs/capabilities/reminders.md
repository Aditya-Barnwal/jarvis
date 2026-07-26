# Capability: Reminders

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "Remind me to call the bank tomorrow at 11", "what's on my list today?", plus Jarvis nudging you proactively.

**Reality:** ✅ clean and local. Two layers: Apple **Reminders.app** (syncs with your iPhone via iCloud, scriptable on the Mac) and Jarvis's own **proactive reminders** (from the daemon's scheduler).

---

## Layer 1 — Apple Reminders (syncs with iPhone)

Reminders you set anywhere (phone, Siri, Mac) live in Reminders.app and sync via iCloud. AppleScript reads and writes them, so a reminder Jarvis creates shows up on your iPhone and fires there too.

```python
# src/tools/reminders.py
import subprocess
from brain import tool

def _osa(s): 
    return subprocess.run(["osascript", "-e", s], capture_output=True, text=True).stdout.strip()

@tool({"name": "add_reminder",
       "description": "Add a reminder, optionally with a due date/time (natural language ok).",
       "parameters": {"type": "object",
           "properties": {"text": {"type": "string"}, "due": {"type": "string"}},
           "required": ["text"]}})
def add_reminder(text: str, due: str = ""):
    date_clause = f'due date:date "{due}"' if due else ""
    _osa(f'''tell application "Reminders"
        make new reminder with properties {{name:"{text}", {date_clause}}}
    end tell''')
    return {"added": text, "due": due or None}

@tool({"name": "todays_reminders",
       "description": "List reminders due today.",
       "parameters": {"type": "object", "properties": {}}})
def todays_reminders():
    out = _osa('''tell application "Reminders"
        set today_list to {}
        repeat with r in (reminders whose completed is false)
            copy (name of r) to end of today_list
        end repeat
        return today_list
    end tell''')
    return {"reminders": out}
```

Because it's the local Reminders.app, listing today's reminders works **offline**; a new reminder syncs to the phone once you're back online (and stays local until then).

## Layer 2 — Jarvis proactive reminders (the daemon nudges you)

Beyond Apple's reminders, the daemon itself can speak up — this is the Phase 6 scheduler ([../phases/phase-6-proactive.md](../phases/phase-6-proactive.md)). Use it for spoken, context-aware nudges that a plain reminder can't do:

- "It's 6pm — your gym block. Want me to start your workout playlist?"
- "You said you'd finish Hull chapter 5 today; it's 9pm and no session logged yet."
- Morning: "Three things due today: call the bank, submit the form, mock interview at 4."

The difference: Apple Reminders are static alarms; Jarvis's proactive reminders are *reasoned* — they pull from your routine, progress, and calendar, and they talk.

## Natural-language timing

You speak "remind me tomorrow morning"; the brain resolves that to a concrete datetime before calling `add_reminder`. The model does the parsing, so you never phrase it rigidly.

## Constraints

- **iCloud Reminders on** for iPhone sync (same as Notes).
- First use → macOS **Automation permission** prompt for Reminders.app. One-time.
- AppleScript date handling is finicky across locales; the real implementation formats dates explicitly rather than trusting string coercion.

## Example

```
You: "Remind me to call the bank tomorrow at 11."
Jarvis: "Done — 'call the bank' tomorrow at 11am. It'll ping on your phone too."
```
