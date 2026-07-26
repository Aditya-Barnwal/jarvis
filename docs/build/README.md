# Jarvis — Implementation docs (what's actually built)

This folder documents the **real, working code** in `src/` — as opposed to the
original planning docs in `../phases/` and `../capabilities/` (the blueprint).
Written so another model/CLI or a human can pick this up cold.

## One-paragraph summary

Jarvis is a **hands-free voice assistant** that runs on a macOS (M1, 8 GB) machine.
You say **"Hey Jarvis"**, it transcribes your speech locally (whisper.cpp), sends the
text to a **brain** (Groq `openai/gpt-oss-20b` online, Ollama `qwen2.5:7b` offline)
along with a set of **tools**, runs whatever tool the brain picks, and **speaks** the
reply in a natural British voice (Kokoro TTS). It knows the time/weather/battery, sees
your screen, controls the Mac, searches the web, drafts email, writes/runs code (with a
confirmation gate), remembers facts about you, and has two personas — **Jarvis**
(professional) and **Friday** (personal).

## The doc set

| Doc | What it covers |
|---|---|
| [architecture.md](architecture.md) | Runtime flow, the brain, tool dispatch, the confirmation gate |
| [voice-ears-audio.md](voice-ears-audio.md) | Voice (Kokoro/personas), ears (wake word/VAD/whisper), barge-in, sleep, audio design |
| [tools.md](tools.md) | The 42-tool catalog by category + how to add one |
| [setup-run-permissions.md](setup-run-permissions.md) | Install, models, macOS permissions, running, the login daemon, env vars |
| [ISSUES.md](ISSUES.md) | **Living list of known issues/limitations** (RAM, audio, GPS…) — kept updated |
| [ANALYSIS.md](ANALYSIS.md) | **Deep review (2026-07-18)**: critical bugs, security loopholes, UX gaps, the 8 GB RAM plan, free upgrades — with a prioritized fix order |

## Source layout (`src/`)

```
config.py         env + model choices (Groq gpt-oss-20b / Ollama qwen2.5:7b), voice lang
connectivity.py   is_online() — routes brain online/offline
brain.py          get_client, run_turn (tool dispatch), tool registry, confirmation gate
voice.py          Voice — warm streaming Kokoro TTS (synth+play threads), warmup/unload/stop
engine_kokoro.py  Kokoro adapter (synth, unload)   engine_chatterbox.py  dormant cloning adapter
voice_state.py    VoiceState (name/voice/emotion/pitch/rate) + persistence
personas.py       Jarvis (professional) + Friday (personal)
lang.py           detect_lang (en/hi) for per-utterance language
ears.py           wake word (openWakeWord) + VAD (silero) + whisper.cpp STT + barge-in
memory.py         local SQLite: facts + learned facts + build_context()
listen.py         THE daemon loop — hands-free wake→talk→sleep, personas, gate, barge-in
hello_jarvis.py   one-shot: text in → voice out    talk.py  press-to-talk loop
miccheck.py       mic/wake/VAD diagnostic
tools/            one file per capability group (see tools.md)
```

## Current status

- **Phase 1 (voice backbone) complete** — wake word, STT, brain, TTS, warm login daemon.
- **42 tools** across time/weather/location, device awareness, Mac control, screen vision,
  web + Gmail, admin/coding (gated), memory, and voice control.
- **Brain**: Groq `gpt-oss-20b` online (fast, clean tool-calls, free) / Ollama `qwen2.5:7b`
  offline. **Voice**: Kokoro `bm_george` (Jarvis) / `bf_emma` (Friday).
- See [ISSUES.md](ISSUES.md) for the honest list of what's rough (mostly 8 GB RAM limits).
</content>
