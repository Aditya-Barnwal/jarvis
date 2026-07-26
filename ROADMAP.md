# Roadmap

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [docs/build/](docs/build/).

Six phases. Each one ends with something you can actually use — no phase is dead weight waiting on the next. Build in order; the dependencies are real (you can't dispatch tools before you have a brain loop).

Rough total: ~9–10 weeks of evenings, but you get a usable assistant after Phase 1.

---

## Phase 1 — Voice backbone  ·  ~2 weeks

The core loop: wake word → Whisper → brain (Groq/Ollama) → Kokoro. Fully local except the brain.

**Ends with:** you say "Hey Jarvis", it hears you, thinks, and talks back hands-free.

Milestones: (1) talk-back only ~20 lines → (2) add ears (Whisper) → (3) wake word + VAD → (4) warm daemon at ~2–3s/turn.

→ [docs/phases/phase-1-voice-backbone.md](phases/phase-1-voice-backbone.md)

## Phase 2 — Memory  ·  ~1.5 weeks

Persistent recall so conversations aren't amnesiac. Session summaries, facts, preferences.

**Ends with:** Jarvis remembers what you told it yesterday and uses it today.

→ [docs/phases/phase-2-memory.md](phases/phase-2-memory.md)

## Phase 3 — Mac control + first tools  ·  ~1.5 weeks

The tool-dispatch pattern goes live. Control apps, volume, Spotify, files via AppleScript. This is where "assistant" becomes "does things".

**Ends with:** "open Spotify and play something", "turn the volume down", "what's in my clipboard" all work.

→ [docs/phases/phase-3-mac-control.md](phases/phase-3-mac-control.md)

## Phase 4 — Browser automation  ·  ~2 weeks

Playwright, run locally. Search Google, read pages, fill forms — with a human gate on anything that writes.

**Ends with:** "look up X and summarize it", "check this website" work; online fallback for questions.

→ [docs/phases/phase-4-browser-automation.md](phases/phase-4-browser-automation.md)

## Phase 5 — Life tools  ·  ~2 weeks

The capabilities that make it *yours*: stocks, expenses, routine/progress, messaging drafts + grammar. Each is a tool module.

**Ends with:** "how's the market", "where did my money go", "what should I do now", "draft a WhatsApp and fix the grammar" all work.

→ [docs/phases/phase-5-life-tools.md](phases/phase-5-life-tools.md)
(Individual specs live in [docs/capabilities/](capabilities/).)

## Phase 6 — Proactive + integrations  ·  ~1 week

Jarvis stops only reacting and starts *initiating*: morning briefings, progress nudges, job-copilot integration, scheduled check-ins.

**Ends with:** an unprompted morning briefing — "19 companies indexed, 3 new job matches, gym in 40 minutes, TCS down 0.6%, quant prep on track."

→ [docs/phases/phase-6-proactive.md](phases/phase-6-proactive.md)

---

## Dependency graph

```
Phase 1 (voice)
   └─▶ Phase 2 (memory)
          └─▶ Phase 3 (mac control + tool dispatch)   ◀── unlocks ALL capabilities
                 ├─▶ Phase 4 (browser)
                 ├─▶ Phase 5 (life tools)
                 └─▶ Phase 6 (proactive)
```

Phase 3 is the keystone — once tool dispatch works, every capability in Phase 5 is independent and can be built in any order (or in parallel on different evenings).

## Where to start tonight

Phase 1, Milestone 1. It's ~20 lines and ends with you hearing Jarvis speak. Everything else is built on the confidence of that first "it works".
