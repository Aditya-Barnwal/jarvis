# Jarvis

A local-first, Iron Man-style personal AI assistant that runs on an M1 MacBook Air.

Voice in, voice out. It listens, thinks, speaks, remembers, controls the Mac, browses the web, and connects to the tools and services you already use — while keeping your data on your machine.

---

## What this repo is

This is the Jarvis workspace: **working code in `src/`** plus its documentation. The root
docs (VISION/ARCHITECTURE/ROADMAP/…) are the original planning blueprint (marked as such);
**[docs/build/](docs/build/)** documents what is actually built and current.

## How to navigate

Start here, then read in this order:

1. **[VISION.md](VISION.md)** — the full "proper Jarvis" scope, honestly scoped. What it will do, and where reality pushes back.
2. **[ARCHITECTURE.md](ARCHITECTURE.md)** — the system design. The daemon, the tool-dispatch pattern, online vs. offline behavior.
3. **[ROADMAP.md](ROADMAP.md)** — the phased build plan. Six phases, each independently useful.
4. **[SETUP.md](SETUP.md)** — install everything the stack needs, once.
5. **[OFFLINE.md](OFFLINE.md)** — how Jarvis keeps working with no internet.
6. **[LEARNING.md](LEARNING.md)** — how it learns from you and from the web.
7. **[docs/phases/](docs/phases/)** — one deep-dive per phase, with build milestones.
8. **[docs/capabilities/](docs/capabilities/)** — one spec per capability (WhatsApp, stocks, expenses, routine, calls, grammar).
9. **[DECISIONS.md](DECISIONS.md)** — why each tool was chosen over the alternatives.

## The one-line mental model

> Jarvis is a **persistent Python daemon** that owns your microphone. It routes everything through **the brain** (Groq online, Ollama offline), which decides whether to *talk*, *remember*, or *call a tool*. Tools are just Python functions — controlling the Mac, reading your calendar, checking a stock, drafting a WhatsApp message — that the brain invokes and narrates.

Everything in this repo is an expansion of that sentence.

## Core principles (inherited from job-copilot)

These four rules shape every design decision. They're the reason some "obvious" features are built the careful way:

- **Local-first & private** — your data (voice, expenses, routine, resume) never leaves the machine unless *you* send it. The only outbound call is to Groq for reasoning (free tier), and even that has a local Ollama fallback.
- **Human-in-the-loop for anything irreversible** — Jarvis drafts, you approve. It never auto-sends a message, auto-submits a form, or spends money without a confirmation gate.
- **Ban-safe** — no automation that violates a service's terms in a way that gets your account banned. Where a "cool" approach is risky (looking at you, WhatsApp), we use the safe path and say so plainly.
- **No fabrication** — when Jarvis reports a number (an expense total, a stock price, your progress), it comes from real data, not a guess.

## Status

**Working hands-free voice assistant with 38 tools.** Say "Hey Jarvis" (or "Friday") → it
transcribes locally, thinks (Groq `gpt-oss-20b` online / Ollama `qwen2.5:7b` offline), runs a
tool, and speaks back in a British voice.

- **Voice backbone (Phase 1) complete** — wake word (openWakeWord) → VAD (Silero) → STT
  (whisper.cpp `small.en`) → brain → **Kokoro** TTS. Warm login daemon (`scripts/`).
- **Two personas** — **Jarvis** (professional) / **Friday** (personal); switch by addressing them.
- **42 tools** — time/weather/location + GPS **distances** (Google-Maps-accurate, states the
  matched place), device awareness, Mac control, **screen vision**, **stocks**, **Apple
  Reminders/Notes**, web search + **Gmail compose**, **install apps / write & run code**
  (confirmation-gated, abortable mid-flight), memory, live voice controls.
- **Conversation mode** (keep talking ~2 min, no repeat wake), **sleep-on-idle** (frees RAM),
  **cross-session memory** (remembers what you talked about yesterday).

> **Full implementation docs live in [docs/build/](docs/build/)** — architecture, voice/audio,
> the tool catalog, setup/permissions, and a living **[ISSUES.md](docs/build/ISSUES.md)**.
> Those describe the real code; the `docs/phases/` + `docs/capabilities/` files are the
> original blueprint.

## Run it

```bash
source .venv/bin/activate
python src/hello_jarvis.py "…"     # one-shot text in, voice out
python src/listen.py               # hands-free: "Hey Jarvis", then keep talking
python src/listen.py friday        # Friday persona
```

**Always-on daemon (runs at login, models stay warm):**
```bash
bash scripts/install-daemon.sh     # start now + at every login  (needs mic permission)
bash scripts/uninstall-daemon.sh   # stop and remove
tail -f logs/daemon.out.log        # watch it
```

**Conversation mode:** after "Hey Jarvis", keep talking with no wake word for up to 2 min
of silence (`JARVIS_FOLLOWUP_WINDOW`); "that's all" / "sleep" ends it. `JARVIS_FOLLOWUP=0` disables.

**Barge-in:** `JARVIS_BARGE_IN` = `off` (default), `wake` (say "Hey Jarvis" to cut him off),
or `voice` (headphones: just talk over him).

**Wake sensitivity:** `JARVIS_WAKE_THRESHOLD=0.4` (lower = triggers from farther).
