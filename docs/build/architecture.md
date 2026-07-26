# Architecture — the runtime

## The loop (`src/listen.py`)

`listen.py` is the daemon. One process, models loaded once, runs forever:

```
start: load wake word + VAD, warm the voice model
loop:
  ── asleep ── poll_wake(15s):  listen only for "Hey Jarvis"
  │              └─ if idle > JARVIS_SLEEP_AFTER (default 300s): unload voice model (free RAM)
  ── awake  ── capture(): record until you stop talking (Silero VAD)
  │            transcribe (whisper.cpp) → text
  │            ├─ persona switch? ("Friday, …" / "Jarvis, …")
  │            ├─ sleep word? ("that's all") → back to asleep
  │            ├─ pending gated action? → treat text as yes/no
  │            └─ else: run_turn(text)  → reply
  │            release mic → speak reply (full audio quality) → reopen mic
  └─ conversation mode: after a reply, keep listening without the wake word
                        (~6s silence → back to asleep)
```

Key behaviours:
- **Wake word** = openWakeWord "hey_jarvis". Sleep/wake like Siri: idle = only the tiny
  wake model runs; brain/STT/TTS are dormant.
- **Conversation mode** (`JARVIS_FOLLOWUP=1`): after waking once, keep talking; no repeat wake.
- **Deep sleep** (`JARVIS_SLEEP_AFTER`): after N idle seconds, unload the voice model to free
  RAM; it reloads (~3.5s) on next wake.
- **Personas**: address "Friday" (personal) or "Jarvis" (professional) to switch voice+prompt.

### Hard-won runtime properties (added 2026-07-19)

- **Mic is NEVER closed mid-session**: one callback-fed stream; pause/resume is a software
  gate (per-turn open/close wedged CoreAudio → the stall saga). 
- **Everything in the speak path is time-bounded** (playback watchdog, wait ceiling, close
  timeout) — a wedge can cost one reply, never freeze the daemon. Stages >2s print [trace].
- **Session memory**: rolling in-session history (follow-ups work) + per-session summaries
  persisted to SQLite and injected next session; auto-consolidated when they pile up.
- **Gated actions run in the background** and can be ABORTED mid-flight ("stop"/"abort").
- **Argument sanitizers** (`brain.sanitizer`) enforce in code what models break in prompt
  (invented weather cities, spelled-out place names).
- **STT hints**: whisper is biased with the user's recent words + known place names —
  never the assistant's replies (hint-echo caused hallucinated turns under noise).

## The brain (`src/brain.py`)

One OpenAI-compatible code path for both backends (`get_client`):
- **Online**: Groq `openai/gpt-oss-20b` (chosen for reliable tool-calling; llama-3.3-70b was
  flaky — emitted malformed `<function=…>` text). Fast (~0.5–1s), free tier.
- **Offline**: Ollama `qwen2.5:7b` (95% tool-routing in tests vs llama3.2:3b's 29%).
- Routing: `use_groq()` = has a GROQ key AND `is_online()`. Else Ollama.

### `run_turn(user_text, system)` — the dispatch loop

1. Build messages: system prompt (persona + emotion + memory context + a capabilities nudge)
   + user text.
2. Call the model with `TOOL_SCHEMAS`. It replies with text or `tool_calls`.
3. For each tool call → `_dispatch(name, fn, args)` → run it, feed the result back, loop
   (bounded to 4 iterations), then return the final spoken text.
4. **Robustness**: catches Groq's `tool_use_failed` 400 (retries without tools) and parses the
   `<function=name {args}>` text-format fallback some models emit.

### Tool registry

Tools register via the `@tool(spec)` decorator (`spec` = OpenAI function schema):
`TOOLS` (name→callable) + `TOOL_SCHEMAS` (what the model sees). Adding a capability =
write a function, decorate it, import its module in `listen.py`. That's it.

### The confirmation gate

Consequential tools are gated: `gate("install_app", "run_command")`. When the brain calls
a gated tool, `_dispatch` does **not** run it — it stores the call in `brain.PENDING` and
returns "confirmation_required", so the reply asks you to confirm. The next utterance is
read as yes/no by `listen.py`: yes → `confirm_pending()` runs it; no → `cancel_pending()`.
This is the human-in-the-loop safety line.

## Online vs offline

| Part | Online | Offline |
|---|---|---|
| Wake word / VAD / STT / TTS | local | same |
| **Brain** | Groq gpt-oss-20b | Ollama qwen2.5:7b |
| Web / Gmail / weather / vision-model-pull | works | skipped or last-known |

The brain is remote online, so it costs **0 local RAM** — critical on 8 GB (see
[ISSUES.md](ISSUES.md)).
