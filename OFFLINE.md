# Offline

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [docs/build/](docs/build/).

Jarvis is built to keep working with **no internet**. This is a first-class design goal, not an afterthought — the daemon detects connectivity and adapts, and most of what makes Jarvis *yours* is local data that never needed the internet in the first place.

---

## What changes when you go offline

Exactly two things degrade; everything personal keeps working.

| Subsystem | Online | Offline |
|---|---|---|
| Wake word | local | ✅ same |
| Speech-to-text (Whisper) | local | ✅ same |
| Text-to-speech (Kokoro) | local | ✅ same |
| **Brain** | Groq (fast, 70B+) | ⚠️ **Ollama `qwen2.5:7b`** — still converses & calls tools, just less clever |
| Mac control | local | ✅ same |
| Memory / recall | local | ✅ same |
| Notes & Reminders | local (iCloud-synced) | ✅ reads last-synced data |
| Screen Time | local DB | ✅ same |
| Expenses (from local data) | local | ✅ same |
| Stocks & markets | live API | ❌ needs internet (uses last cached quote + says so) |
| Web search / browsing | Groq search / Playwright | ❌ needs internet (skips gracefully) |
| Learning *from the internet* | yes | ❌ paused until back online |
| Learning *from you* | yes | ✅ same |

The headline: **the assistant that knows your routine, your expenses, your notes, your habits, and controls your Mac works completely offline.** Only the "reach out to the world" features pause.

## How the daemon handles it

At startup and on network changes, the daemon runs a fast reachability check and sets a flag:

```python
# src/connectivity.py
import socket

def is_online(host="api.groq.com", port=443, timeout=1.5) -> bool:
    try:
        socket.create_connection((host, port), timeout=timeout)
        return True
    except OSError:
        return False
```

That flag does two things:

1. **Brain routing** — `get_client(online)` returns Groq when up, Ollama when down. Same OpenAI-compatible call either way (see [ARCHITECTURE.md](ARCHITECTURE.md)).
2. **Tool gating** — internet-only tools (stocks, web) are hidden from the tool list when offline, so the brain doesn't try to call them. Instead of hanging, Jarvis says "I can't reach the markets right now — last I saw, TCS was ₹3,842."

## The offline brain, honestly

`qwen2.5:7b` on Ollama is genuinely capable for a 7B — it holds a conversation, follows instructions, and does tool calling. But it is not Groq's 70B. Expect:

- Simpler phrasing, occasional clumsiness on multi-step reasoning.
- Tool calls still work (Qwen supports them), so "open Spotify", "what's my next reminder", "how much did I spend yesterday" all function offline.
- Long, nuanced reasoning ("analyze my spending trends and suggest what's driving the increase") is where you'll feel the gap — those answers are sharper online.

If you want a stronger offline brain and have the RAM, you can pull a bigger Ollama model (e.g. a 14B) and point the offline path at it — one line in `get_client`. On an 8GB Air, `qwen2.5:7b` is the practical ceiling; on 16GB you have room for more.

## Why so much works offline: local-first by design

Every personal capability reads **data that already lives on your Mac**:

- Notes & Reminders → Apple's local stores (iCloud syncs them *to* the Mac; reading is local).
- Screen Time → local `knowledgeC.db`.
- Expenses → transaction SMS in local `chat.db`, or a CSV you dropped in `data/`.
- Memory → local SQLite.

None of these needed the cloud to *read*. That's the whole local-first payoff: your assistant doesn't go dark when your Wi-Fi does.
