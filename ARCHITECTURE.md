# Architecture

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [docs/build/](docs/build/).

The whole system is one long-running Python process (the **daemon**) that owns your microphone and coordinates everything else. This document explains how the pieces fit, and — most importantly — the **tool-dispatch pattern** that makes every future capability just a matter of writing one function.

---

## The daemon

A single `asyncio` process that stays running (launched at login via `launchd`). It:

1. Holds the microphone stream open.
2. Keeps every model warm in memory (Whisper, wake word, Kokoro) so there's no cold-start cost per turn.
3. Owns the conversation state and the memory store.
4. Runs the listen → think → speak → act loop forever.

Why one process: loading Whisper and Kokoro takes seconds. If you reload them every turn, every reply is slow. Keeping them resident is the single biggest latency win — it's the difference between ~10s and ~2–3s per turn.

## The loop

```
        ┌──────────────────────────────────────────────┐
        │                  DAEMON                        │
        │                                                │
  mic ──▶ wake word ──▶ record+VAD ──▶ Whisper (STT)    │
        │                                    │           │
        │                                    ▼           │
        │                          ┌──────────────────┐  │
        │                          │  BRAIN (Groq /   │  │
        │                          │  Ollama)         │  │
        │            memory ◀──────┤  decides: talk?  │  │
        │            context       │  remember? tool? │  │
        │                          └────────┬─────────┘  │
        │                    ┌───────────────┼─────────┐ │
        │                    ▼               ▼         ▼ │
        │                 speak         call tool   store │
        │              (Kokoro TTS)    (dispatch)   memory│
        │                    │                            │
        └────────────────────┼────────────────────────────┘
                             ▼
                          speaker  ──▶ back to listening
```

## The tool-dispatch pattern (the important part)

This is the design that makes Jarvis extensible. Every capability — checking a stock, controlling volume, drafting a message — is a **Python function** exposed to the brain as a *tool*. The flow:

1. You speak. Whisper turns it into text.
2. The daemon sends that text to the brain **along with the list of available tools** (standard OpenAI-style function-calling).
3. The brain decides what to do. It returns either:
   - a **text reply** → the daemon speaks it, or
   - a **tool call** (a function name + JSON arguments) → the daemon runs that function, feeds the result back, and the brain produces the final spoken reply.

The brain is **Groq online, Ollama offline** — and crucially both speak the *same* OpenAI-compatible tool format, so this flow is one code path regardless of which backend is active.
4. Result is spoken via Kokoro, and the exchange is written to memory.

Concretely, a tool is just:

```python
def get_stock_quote(symbol: str) -> dict:
    """Return the latest price and day change for a ticker."""
    # ... hit a free market-data API ...
    return {"symbol": symbol, "price": 3842.10, "change_pct": -0.6}

TOOLS = {
    "get_stock_quote": get_stock_quote,
    "control_volume": control_volume,
    "draft_message": draft_message,
    "read_routine": read_routine,
    # ... every new capability adds one line here ...
}
```

You describe each tool to the brain as an OpenAI-style function schema, the brain picks the right one and returns a `tool_calls` request, your dispatcher looks it up in `TOOLS` and runs it. **Adding a capability = write a function + add one schema entry.** That's the whole extensibility story.

> The OpenAI function-calling format (`{"type":"function","function":{...}}` → model returns `tool_calls` → you reply with a `role:"tool"` message) is the contract here, and both Groq and Ollama honor it. Skim the current Groq tool-use docs once so the field names are exactly right. Full working dispatch code is in [docs/phases/phase-3-mac-control.md](docs/phases/phase-3-mac-control.md).

## Online vs. offline

Jarvis degrades gracefully instead of breaking:

| Component | Online | Offline |
|---|---|---|
| Wake word | local | local (no change) |
| STT (Whisper) | local | local (no change) |
| **Brain** | **Groq (`llama-3.3-70b-versatile`)** | **Ollama (`qwen2.5:7b`)** |
| TTS (Kokoro) | local | local (no change) |
| Web tools | available | skipped with a spoken note |

Only the brain and web-dependent tools care about connectivity. The daemon checks reachability and swaps the brain backend transparently. Offline Jarvis is dumber (a local 7B vs. a 70B on Groq) but still converses and controls your Mac.

## Memory

A local store (SQLite to start; ChromaDB later if you want semantic recall) holds:

- **Session summaries** — compressed history so the brain has continuity without re-sending everything.
- **Facts & preferences** — "I go to the gym at 6am", "my main project is quant prep".
- **Entity notes** — people, projects, recurring things.

Every brain call gets relevant memory injected as context. This is what makes it feel like it *knows* you rather than resetting every conversation. Full detail in [docs/phases/phase-2-memory.md](phases/phase-2-memory.md).

## Directory layout (once code exists)

```
jarvis/
├── README.md, VISION.md, ARCHITECTURE.md, ...   # these docs
├── docs/
│   ├── phases/
│   └── capabilities/
└── src/                      # appears in Phase 1
    ├── daemon.py             # the asyncio loop
    ├── brain.py              # Groq / Ollama backend + tool dispatch
    ├── ears.py               # wake word + VAD + Whisper
    ├── voice.py              # Kokoro TTS
    ├── memory.py             # SQLite / Chroma store
    └── tools/                # one file per capability
        ├── mac_control.py
        ├── stocks.py
        ├── expenses.py
        ├── routine.py
        ├── messaging.py
        └── ...
```

## Security posture

- Secrets (`GROQ_API_KEY`, any Twilio/API keys) live in a `.env` file that is **git-ignored**, never in code.
- Nothing that enters banking or card credentials is automated — ever. Jarvis can *read* an expense CSV you exported; it does not log into your bank.
- Any tool with a side effect (send, spend, delete) routes through a **confirmation gate** before executing.
