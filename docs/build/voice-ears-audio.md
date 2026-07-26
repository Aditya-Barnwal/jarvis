# Voice, ears & audio

## Voice — TTS (`src/voice.py`, `engine_kokoro.py`)

- **Engine**: Kokoro (`kokoro` pip pkg), Apple-Silicon-friendly, fully local. British voices:
  `bm_george` (Jarvis), `bf_emma` (Friday). Engine is swappable via `JARVIS_TTS_ENGINE`
  (a dormant `engine_chatterbox.py` cloning adapter exists but is not active — it conflicts
  with torch/numpy versions; would need an isolated venv).
- **Pipeline**: two threads — a **synth worker** and a **play worker** — so `say()` returns
  instantly and audio plays in the background. `say()` enqueues the **whole reply as one piece**
  (gapless — no mid-sentence stutter).
- **Warm/unload**: `warmup()` pre-loads Kokoro at startup (avoids a ~9s cold-load on first
  reply). `unload()` frees it for deep sleep; reloads in ~3.5s.
- **Interruptible**: `stop()` halts playback + clears the queue (for barge-in).
- **Live controls** (via tools): `set_emotion`, `set_pitch`, `set_rate`, `set_voice`,
  `rename_self` mutate `VoiceState` (`voice_state.py`); pitch/rate applied via pedalboard DSP.

## Ears — STT (`src/ears.py`)

- **Wake word**: openWakeWord "hey_jarvis" (ONNX). Threshold `JARVIS_WAKE_THRESHOLD` (0.5).
- **VAD**: Silero `VADIterator` auto-stops recording when you finish talking.
- **STT**: whisper.cpp (`whisper-cli`) — model **`small.en`** (auto-preferred if present; more
  accurate in noise/earphones than `base.en`). Override via `WHISPER_MODEL`.
- **Persistent stream**: the mic opens once (`start()`) and stays warm across turns
  (`poll_wake`, `capture`). `pause()`/`resume()` close+reopen the mic around speech.

## Audio design decisions (learned the hard way — see ISSUES.md)

1. **Mic released while speaking** (barge-in `off`, the default): a *live* mic makes macOS drop
   the speakers into low-quality "communication" mode. So `listen.py` calls `pause()` (closes
   the mic) before speaking and `resume()` after → full-quality British voice. Cost: ~0.4s
   reopen between turns.
2. **Barge-in** (`JARVIS_BARGE_IN`): `off` (best audio, default), `wake` (say "Hey Jarvis" to
   cut in — echo-safe on speakers), `voice` (headphones: talk over him). Keeping the mic open
   for barge-in degrades speaker audio on macOS, so it's opt-in.
3. **Wake-model reset on barge monitor**: without it, the just-said "hey jarvis" re-fired
   instantly (false "you cut in" that also killed playback).
4. **No `say` fallback**: macOS `say` was removed entirely — the good voice is always Kokoro.

## Personas (`src/personas.py`)

`Persona` = name + voice + speed + system prompt. **Jarvis** = professional (work, email, code,
tasks). **Friday** = personal (outfits, shopping, entertainment). Switch by addressing them:
"Friday, …" / "Jarvis, …" (`_persona_from` in `listen.py`), which swaps voice + system prompt
mid-conversation.

## Entry points

- `python src/listen.py` — hands-free daemon (the real thing).
- `python src/talk.py` — press-to-talk (Enter to start/stop).
- `python src/hello_jarvis.py "…"` — one-shot text→voice.
- `python src/miccheck.py` — diagnose mic level, wake score, VAD, transcription.
