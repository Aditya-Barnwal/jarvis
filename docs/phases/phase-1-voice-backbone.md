# Phase 1 — Voice backbone

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**Goal:** one working loop — you say "Hey Jarvis", it hears you, thinks, and talks back, fully local except the brain.

Everything else in the roadmap hangs off this. Build it in four small milestones, each independently testable.

---

## The loop

```
mic ──▶ wake word ──▶ record + VAD ──▶ Whisper (STT) ──▶ text
                                                          │
                                                          ▼
                                          brain: Groq (online) / Ollama (offline)
                                                          │
                                                          ▼
text ──▶ Kokoro TTS ──▶ speaker ──▶ (loop back to listening)
```

Everything except the online brain runs offline. Target: ~2–3s per turn after the first, once models stay warm.

## Component picks (see DECISIONS.md for why)

| Stage | Tool | Notes |
|---|---|---|
| Wake word | openWakeWord | stock "hey jarvis" model, ONNX, no key |
| End-of-speech | Silero VAD | stops recording when you go quiet |
| STT | whisper.cpp `base.en` | Metal-accelerated, ~0.5s |
| Brain (online) | Groq `llama-3.3-70b-versatile` | free tier, very fast |
| Brain (offline) | Ollama `qwen2.5:7b` | local fallback |
| TTS | kokoro-mlx | voice `am_puck` or `af_heart` |

---

## Milestone 1 — Talk-back (do this first, ~20 lines)

Hardcode a message, send it to the brain, speak the reply. Proves the brain→voice half works and gives you the "it's alive" moment.

```python
# src/hello_jarvis.py
import os
from dotenv import load_dotenv
from groq import Groq
from kokoro_mlx import KokoroTTS

load_dotenv()
client = Groq()                     # reads GROQ_API_KEY from env
tts = KokoroTTS.from_pretrained()

SYSTEM = "You are Jarvis, a concise, warm personal assistant. Keep replies short and speakable."

def ask(text: str) -> str:
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text},
        ],
    )
    return resp.choices[0].message.content

if __name__ == "__main__":
    reply = ask("Introduce yourself in two sentences.")
    print(reply)
    tts.play(reply, voice="am_puck")    # speaks through your speakers
```

Run:

```bash
source .venv/bin/activate
python src/hello_jarvis.py
```

You should hear Jarvis introduce itself. That's the whole point of Milestone 1.

> Two notes: (1) Get a free `GROQ_API_KEY` at console.groq.com/keys and put it in `.env`. (2) Check the current `kokoro-mlx` README for the exact play/stream method name — the API is young and may be `tts.play(...)`, `tts.speak(...)`, or `tts.save(...)` + a separate playback call.

### Offline variant (same code, swap the client)

Because Ollama is OpenAI-compatible, the *only* change to run fully offline is the client target:

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")  # local Ollama
# ... then model="qwen2.5:7b" in the call
```

Identical `chat.completions.create(...)` call. The daemon (Milestone 4) picks online vs. offline automatically based on connectivity.

---

## Milestone 2 — Ears (press-to-talk)

Replace the hardcoded string with real speech. On a keypress, record ~5s, transcribe with whisper.cpp, feed to `ask()`.

Flow: keypress → `sounddevice` records to a WAV → shell out to `whisper-cli` → read the transcript → `ask()` → `tts.play()`.

```python
# sketch
import subprocess, os, sounddevice as sd, scipy.io.wavfile as wav

def record(seconds=5, sr=16000):
    audio = sd.rec(int(seconds*sr), samplerate=sr, channels=1)
    sd.wait()
    wav.write("/tmp/in.wav", sr, audio)

def transcribe():
    subprocess.run(["whisper-cli", "-m",
        f"{os.path.expanduser('~')}/.local/share/whisper-models/ggml-base.en.bin",
        "-f", "/tmp/in.wav", "-otxt", "-of", "/tmp/out"], check=True)
    return open("/tmp/out.txt").read().strip()
```

Now you have a full press-to-talk assistant. Genuinely usable already.

---

## Milestone 3 — Wake word + VAD (hands-free)

Swap the keypress for always-listening. openWakeWord scores every audio frame; when "hey jarvis" crosses the threshold, start recording, and use Silero VAD to auto-stop when you finish speaking.

```python
# sketch
from openwakeword.model import Model
oww = Model(wakeword_models=["hey_jarvis"], vad_threshold=0.5)

# in the mic callback loop:
prediction = oww.predict(frame)
if prediction["hey_jarvis"] > 0.5:
    audio = record_until_silence()   # VAD-gated
    text = transcribe(audio)
    tts.play(ask(text))
```

`vad_threshold` gates wake-word firing on actual speech, cutting false triggers from background noise. Tune the 0.5 to your room.

**Custom "Jarvis" trigger (optional):** the stock model works; if you want a tighter custom wake word, openWakeWord has a training pipeline, or drop in Porcupine (instant, needs a key). Only bother if the stock trigger misfires.

---

## Milestone 4 — Warm daemon

Wrap it all in one `asyncio` process that:

- loads Whisper, Kokoro, openWakeWord **once** at startup,
- holds the mic stream open,
- checks connectivity and picks the Groq (online) or Ollama (offline) brain,
- runs the loop forever,
- (later) launches at login via `launchd`.

This is what drops latency to the ~2–3s target — no per-turn model loading.

```python
# src/daemon.py — skeleton
import asyncio

class Jarvis:
    def __init__(self):
        self.oww = ...      # load once
        self.tts = ...      # load once
        self.brain = ...    # Groq client if online, else Ollama — chosen at startup + on network change

    async def listen_loop(self):
        while True:
            frame = await self.next_audio_frame()
            if self.woken(frame):
                text = await self.transcribe(await self.record_until_silence())
                reply = await self.think(text)     # tool-dispatch added in Phase 3
                await self.speak(reply)

if __name__ == "__main__":
    asyncio.run(Jarvis().listen_loop())
```

By the end of Phase 1 you have a hands-free voice assistant. Phase 2 gives it memory; Phase 3 gives it hands.

---

## Latency budget (what "good" looks like)

| Stage | Target |
|---|---|
| Wake word detection | instant (per-frame) |
| Record + VAD | as long as you talk |
| Whisper base.en | ~0.5s |
| Groq brain round-trip | ~0.3–0.8s (Groq is very fast) |
| Kokoro first audio | ~0.3s (stream sentence-by-sentence) |
| **Perceived total** | **~2s** online, a bit more offline |

Groq's speed is a real advantage here — the brain round-trip is often faster than a local model would be. Biggest lever after that: **stream** Kokoro sentence-by-sentence so you hear the first words while the rest synthesizes.
