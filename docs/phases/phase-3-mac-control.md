# Phase 3 — Mac control + tool dispatch

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**Goal:** the keystone phase. "Assistant" becomes "does things." Once tool dispatch works here, every capability in Phase 5 is just another function.

---

## The tool-dispatch mechanism

This is the single most important pattern in Jarvis. Every capability is a Python function exposed to the brain as a tool. The daemon:

1. Sends your text + the tool schemas to the brain (Groq or Ollama).
2. The brain replies with either text (speak it) or one/more `tool_calls` (name + JSON args).
3. On a tool call, the daemon runs the function, feeds the result back, and the brain produces the final spoken reply.

**One format for both backends.** Groq and Ollama both use the OpenAI-compatible function-calling schema, so this code works unchanged whether you're online or offline — only the client's base URL + model name differ.

```python
# src/brain.py
import json
from groq import Groq
from openai import OpenAI

TOOLS = {}          # name -> python callable
TOOL_SCHEMAS = []   # the JSON schemas the model sees (OpenAI function format)

def tool(spec):
    """Decorator: register a function as a brain-callable tool.
    `spec` = {"name", "description", "parameters"} — the OpenAI function schema,
    where `parameters` is a JSON-schema object describing the args."""
    def wrap(fn):
        TOOLS[spec["name"]] = fn
        TOOL_SCHEMAS.append({"type": "function", "function": spec})
        return fn
    return wrap

def get_client(online: bool):
    if online:
        return Groq(), "llama-3.3-70b-versatile"
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"), "qwen2.5:7b"

def run_turn(user_text, context, online=True):
    client, model = get_client(online)
    messages = [
        {"role": "system", "content": f"You are Jarvis. {context}"},
        {"role": "user", "content": user_text},
    ]
    while True:
        resp = client.chat.completions.create(
            model=model, messages=messages,
            tools=TOOL_SCHEMAS, tool_choice="auto", max_tokens=500,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content                      # plain reply → speak it

        messages.append(msg)                        # record the assistant's tool request
        for call in msg.tool_calls:
            fn = TOOLS[call.function.name]
            args = json.loads(call.function.arguments)
            result = maybe_confirm_and_run(call.function.name, fn, args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })
        # loop back: brain sees the tool results and produces the final reply
```

**Adding a capability = write a function + decorate it.** That's the whole extensibility story.

> This OpenAI-style `tool_calls` / `role: "tool"` shape is exactly what both Groq and Ollama expect. Skim the current Groq tool-use docs once to confirm field names before finalizing — they're stable but worth a glance.

## First tools: Mac control

macOS control is `osascript` (AppleScript) + shell, wrapped as functions.

```python
# src/tools/mac_control.py
import subprocess
from brain import tool

@tool({"name": "control_volume", "description": "Set the Mac output volume (0-100).",
       "parameters": {"type": "object",
           "properties": {"level": {"type": "integer"}}, "required": ["level"]}})
def control_volume(level: int):
    subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
    return {"ok": True, "level": level}

@tool({"name": "open_app", "description": "Open a macOS application by name.",
       "parameters": {"type": "object",
           "properties": {"name": {"type": "string"}}, "required": ["name"]}})
def open_app(name: str):
    subprocess.run(["open", "-a", name])
    return {"ok": True, "app": name}
```

Starter tool set for this phase:

| Tool | Does |
|---|---|
| `control_volume` | set output volume |
| `open_app` | launch any app |
| `spotify_control` | play/pause/next via AppleScript |
| `read_clipboard` | `pbpaste` |
| `write_clipboard` | `pbcopy` |
| `system_status` | battery, wifi, disk via shell |
| `set_reminder` | Reminders.app via AppleScript |

Each is ~5 lines. This is the phase where you feel the leverage.

## The confirmation gate

Tools with side effects (send, spend, delete, anything irreversible) must not fire silently. `maybe_confirm_and_run` wraps them:

```python
GATED = {"send_message", "place_call", "send_sms", "delete_file", "fill_form"}

def maybe_confirm_and_run(name, fn, args):
    if name in GATED:
        speak(f"You want me to {describe(name, args)} — confirm?")
        if not heard_yes():          # waits for a spoken "yes"
            return {"cancelled": True}
    return fn(**args)
```

This mirrors job-copilot's human-approval gate. It's what makes an autonomous-feeling assistant safe to actually let loose.

## Permissions

macOS will prompt for Accessibility / Automation permissions the first time Jarvis controls apps. Grant them under System Settings → Privacy & Security. One-time.

**Ends with:** "open Spotify", "volume to 30", "what's in my clipboard", "how's my battery" all work by voice — and the dispatch pattern is now in place for everything else.
