# Voice engine — cloneable, multilingual, conductable

The goal: **one voice, every language**, that you can **reshape mid-conversation by voice command** — switch the voice, rename the assistant, change pitch/tone/rate, and shift emotion ("be angry", "talk softly", "sound excited"). This doc specs the engine, the live-control layer, and the commands, and is honest about what your M1 Air will and won't do smoothly.

This replaces the Kokoro-only voice layer. Kokoro stays as an optional fast fallback.

---

## Engine choice (2026 landscape)

No single model maxes every axis, so pick a primary and layer control on top. What matters for you: cross-lingual **cloning** (one voice, all languages), **emotion/pitch control**, **Apple-Silicon fit**, and a clean **license**.

| Model | Cloning | Languages | Emotion control | License | M1 fit |
|---|---|---|---|---|---|
| **Chatterbox Multilingual V3** ★ | zero-shot ~5s | 23 | **exaggeration dial + tags** `[laugh]` `[cough]` | **MIT** | 0.5B, runs on MPS; heavier than Kokoro |
| **Qwen3-TTS (MLX)** ★ Apple-native | ~3s | multilingual | **describe-the-voice** ("low, seductive") | Apache-2.0 | MLX build = best M1 path |
| Zonos | yes | multilingual | **8D emotion vector** + `pitch_std`, rate | permissive | heavier |
| XTTS v2 | ~6s | 17 | style/emotion transfer via reference | CPML (non-commercial) | CPU/MPS, slower |
| F5-TTS | ~10s | EN/ZH strong | style transfer via reference | CC-BY-NC | ~3GB, slower |
| Kokoro (current) | none | 8 (voice per lang) | none (speed only) | Apache-2.0 | fastest, tiny |

**Recommendation:**
- **Primary: Chatterbox Multilingual V3.** One cloned voice across languages, MIT license, and the emotion-exaggeration dial is exactly the "be more intense / angry" knob you want.
- **Apple-native alternative: Qwen3-TTS MLX.** If you want lowest latency on the M1 and natural-language voice *description* ("speak in a hushed, seductive tone"), this is the one. Its MLX build is made for Apple Silicon.
- Keep **Kokoro** wired as an optional instant fast-path for short replies where you don't need cloning/emotion.

You can start on one and swap later — they all sit behind the same `Voice.say()` interface.

---

## Architecture: a live VoiceController

Everything mid-conversation-controllable lives in one mutable state object. Commands mutate it; `Voice.say()` reads it each turn.

```python
# src/voice_state.py
from dataclasses import dataclass, field

@dataclass
class VoiceState:
    name: str = "EDITH"            # spoken identity; rename on command
    voice_ref: str = "edith.wav"   # reference clip in data/voices/ (the cloned voice)
    language: str = "auto"         # 'auto' detects per sentence; or force 'hi','en',...
    # expressive controls:
    emotion: str = "neutral"       # neutral|angry|soft|excited|seductive|sad|...
    intensity: float = 0.5         # 0.0–1.0+  (Chatterbox 'exaggeration')
    pitch_semitones: float = 0.0   # DSP pitch shift; +deeper? no: - = deeper, + = higher
    rate: float = 1.0              # speaking rate (0.8 slower … 1.2 faster)

STATE = VoiceState()   # single source of truth, held in the daemon
```

```python
# src/voice.py  (engine-agnostic wrapper)
import re, queue, threading
import sounddevice as sd, numpy as np
from pedalboard import Pedalboard, PitchShift
from voice_state import STATE
from engine_chatterbox import synth   # swap this import to change engines

SENT = re.compile(r'(?<=[.!?।])\s+')   # includes Hindi danda ।

class Voice:
    def __init__(self):
        self._q = queue.Queue()
        threading.Thread(target=self._player, daemon=True).start()

    def _player(self):
        while True:
            audio, sr = self._q.get()
            sd.play(audio, sr); sd.wait()

    def say(self, text: str):
        for sentence in filter(None, SENT.split(text.strip())):
            lang = detect_lang(sentence) if STATE.language == "auto" else STATE.language
            audio, sr = synth(                       # engine call, reads live STATE
                text=sentence, ref=STATE.voice_ref, language=lang,
                emotion=STATE.emotion, intensity=STATE.intensity, rate=STATE.rate,
            )
            if STATE.pitch_semitones:                # DSP pitch shim on top of engine
                audio = Pedalboard([PitchShift(semitones=STATE.pitch_semitones)])(audio, sr)
            self._q.put((audio, sr))
```

```python
# src/engine_chatterbox.py — the swappable engine adapter
from chatterbox.tts import ChatterboxMultilingualTTS
_model = ChatterboxMultilingualTTS.from_pretrained(device="mps")  # load once, keep warm

# map friendly emotions to the engine's dial (+ optional per-emotion reference clips)
_EMO = {"neutral":0.5, "soft":0.3, "seductive":0.4, "sad":0.4, "excited":0.8, "angry":0.9}

def synth(text, ref, language, emotion, intensity, rate):
    exaggeration = _EMO.get(emotion, intensity)
    wav = _model.generate(text, audio_prompt_path=f"data/voices/{ref}",
                          language_id=language if language != "auto" else "en",
                          exaggeration=exaggeration, cfg_weight=0.5)
    return wav, 24000
```

To switch engines (Qwen3-TTS MLX, XTTS, Zonos), you only rewrite `engine_*.py` with the same `synth(...)` signature. Nothing else changes.

---

## The command layer (conduct it mid-conversation)

Each control is a tool the brain maps natural speech to (needs Phase 3 dispatch; until then they're callable functions). The brain hears "talk softer" and calls `set_emotion("soft")`.

```python
# src/tools/voice_control.py
from voice_state import STATE
from brain import tool
import memory

@tool({"name":"set_voice","description":"Switch to a different cloned voice by name.",
       "parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}})
def set_voice(name):
    STATE.voice_ref = f"{name}.wav"; memory.remember("voice_ref", STATE.voice_ref)
    return {"voice": name}

@tool({"name":"rename_self","description":"Change the assistant's name/identity.",
       "parameters":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}})
def rename_self(name):
    STATE.name = name; memory.remember("assistant_name", name)   # persists across restarts
    return {"name": name}

@tool({"name":"set_emotion","description":"Set emotional delivery: neutral, soft, seductive, excited, angry, sad.",
       "parameters":{"type":"object","properties":{
           "emotion":{"type":"string"},"intensity":{"type":"number"}},"required":["emotion"]}})
def set_emotion(emotion, intensity=None):
    STATE.emotion = emotion
    if intensity is not None: STATE.intensity = intensity
    return {"emotion": emotion, "intensity": STATE.intensity}

@tool({"name":"set_pitch","description":"Shift pitch. Negative = deeper, positive = higher. Semitones.",
       "parameters":{"type":"object","properties":{"semitones":{"type":"number"}},"required":["semitones"]}})
def set_pitch(semitones):
    STATE.pitch_semitones = max(-8, min(8, semitones)); return {"pitch": STATE.pitch_semitones}

@tool({"name":"set_rate","description":"Speaking rate. 0.8 slow … 1.2 fast.",
       "parameters":{"type":"object","properties":{"rate":{"type":"number"}},"required":["rate"]}})
def set_rate(rate):
    STATE.rate = max(0.6, min(1.6, rate)); return {"rate": STATE.rate}
```

Now these all work by voice, mid-sentence:

- *"Switch to my voice."* → `set_voice("aditya")`
- *"From now on your name is Vega."* → `rename_self("Vega")` (persists)
- *"Talk to me softly."* / *"Be angry."* → `set_emotion("soft")` / `set_emotion("angry", 0.95)`
- *"Go a bit deeper."* → `set_pitch(-2)`
- *"Slow down."* → `set_rate(0.85)`

Because the brain interprets intent, you don't need exact phrasing — "sound more excited", "drop your voice lower", "call yourself X" all route correctly.

---

## Emotion, done honestly (three levers, stacked)

"Seductive" or "angry" isn't one magic flag — convincing emotion comes from **three layers working together**, which is also why the stacked approach beats any single model:

1. **Engine emotion** — Chatterbox's `exaggeration` dial (or Zonos's 8D emotion vector, or Qwen3's text description). This colors the acoustic delivery.
2. **Register in the words** — the brain rewrites *what* it says to match. Angry EDITH uses clipped, blunt sentences; seductive EDITH slows and softens word choice. Half of perceived emotion is phrasing + punctuation, and this is free — just a system-prompt instruction tied to `STATE.emotion`.
3. **Pitch & rate (DSP)** — deterministic shaping on top: angry → slightly faster, flatter; soft/seductive → lower pitch, slower rate.

Stronger emotion option: keep a few **reference clips per emotion** of the same voice (`edith_neutral.wav`, `edith_soft.wav`, `edith_angry.wav`) and switch which one conditions cloning — the model then *imitates* that emotional delivery directly. Best results, a little more setup.

If emotion precision becomes the priority, **Zonos** is the specialist: emotion is an explicit vector (you dial happy/sad/angry/… independently) alongside `pitch_std` and rate — the finest control in the open field. Swap it in behind `synth(...)` if you want that.

---

## One voice, every language

With a cloning engine, the reference clip defines the voice and the `language` argument defines what it speaks — the timbre stays constant across languages (this is the whole point vs. Kokoro's per-language voices). Per sentence:

```python
import re
DEVANAGARI = re.compile(r'[\u0900-\u097F]')
def detect_lang(text):
    letters=[c for c in text if c.isalpha()]
    if not letters: return "en"
    return "hi" if sum(bool(DEVANAGARI.match(c)) for c in letters)/len(letters)>0.3 else "en"
```

Extend the detector for other scripts as you add languages. For mixed Hinglish in one sentence, split on script runs and synthesize each run with the same voice ref but the right `language_id`.

---

## Voice registry (and the one rule)

Drop reference clips (~5–15s, clean, mono) in `data/voices/`:

```
data/voices/
  edith.wav        # your default assistant voice
  aditya.wav       # your own voice (record 30s)
  friday.wav
  edith_angry.wav  # optional emotion references
```

Switch by name via `set_voice`. **The one rule:** these are voices you're entitled to use — **your own**, someone who's **agreed**, or a **licensed/royalty-free** pack. That's the only constraint on the registry; within it, anything goes.

---

## Reality on an M1 Air (so nothing surprises you)

Not a limitation to design around — just plan for it:

- These cloning models are **heavier than Kokoro**. Chatterbox (0.5B) on MPS synthesizes well but not Kokoro-instant; expect a few hundred ms to ~1s per sentence, more the first time. Streaming sentence-by-sentence (already in `Voice`) hides most of it.
- **8GB is tight** to hold Chatterbox + Ollama's 7B + Whisper all warm at once. Practical options: (a) keep **Kokoro as the fast default** and use Chatterbox only for expressive/cloned moments; (b) run the brain on **Groq** (remote, 0 local RAM) so local RAM is free for the voice model; (c) 16GB+ if you later upgrade makes it comfortable. Option (b) pairs perfectly with your existing Groq-online / Ollama-offline setup — online, the voice model has the RAM it needs.
- **Qwen3-TTS MLX** is the lightest-latency cloning path on Apple Silicon specifically — worth benchmarking against Chatterbox on your machine and keeping whichever feels better.

---

## CLI task spec (paste to your agent)

```
Working in the jarvis project. Replace the Kokoro-only voice layer with a
cloneable, multilingual, live-controllable engine. Keep warm+streaming design.

TASK 1 — Engine
- Add engine_chatterbox.py using Chatterbox Multilingual V3 (pip install chatterbox-tts),
  device="mps", model loaded ONCE at startup. Implement synth(text, ref, language,
  emotion, intensity, rate) -> (audio, sr). Map emotions to the exaggeration dial.
- (Alt to benchmark: engine_qwen3.py using Qwen3-TTS MLX. Same synth() signature.)

TASK 2 — Live state + wrapper
- Add voice_state.py (VoiceState dataclass + STATE singleton) exactly as specced.
- Rewrite voice.py to read STATE each turn, stream sentence-by-sentence (split on
  [.!?।]), route language via detect_lang(), and apply pedalboard PitchShift when
  STATE.pitch_semitones != 0. Engine import at top so it's swappable.

TASK 3 — Voice registry
- Create data/voices/. Add edith.wav (default). Support switching refs by filename.
- Document the consent rule in a README in that folder (own/consented/licensed only).

TASK 4 — Command tools (functions now; dispatched tools once Phase 3 lands)
- Add tools/voice_control.py: set_voice, rename_self, set_emotion, set_pitch, set_rate,
  each mutating STATE and (for name/voice) persisting via memory.remember so they
  survive restarts.
- Tie STATE.emotion into the brain system prompt so the WORDS match the emotion
  (angry=clipped/blunt, soft/seductive=slower/softer phrasing).

TASK 5 — Wire + test
- hello_jarvis.py: after each brain reply, if it contained a control command, apply it,
  then speak in the current STATE. Manual tests:
  * English then Hindi sentence -> same voice, correct language.
  * "be angry" then a line -> higher intensity + clipped phrasing.
  * "go deeper" -> pitch drops. "call yourself Vega" -> name persists after restart.
- Report per-sentence latency on your M1 for Chatterbox vs Qwen3-TTS MLX so we pick.

NOTE: if RAM is tight, run the brain on Groq (online) so the voice model has headroom;
keep Kokoro as an optional instant fast-path for short non-expressive replies.
```

---

### What each of your asks maps to

- *any language, one voice* → cloning engine + per-sentence `language` routing.
- *change voice mid-convo* → `set_voice` + the registry.
- *change the name* → `rename_self` (persisted to memory).
- *change tone/pitch* → `set_pitch` / `set_rate` (DSP) + engine.
- *seductive / angry / any emotion* → `set_emotion` (engine dial + brain register + optional emotion reference clips).
