# Setup

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [docs/build/](docs/build/).

One-time environment setup for the whole stack on an M1 MacBook Air. Do this once; every phase assumes it's done.

Verified against the current local-voice stack for Apple Silicon (mid-2026).

---

## Prerequisites

- macOS on Apple Silicon (M1 or later)
- [Homebrew](https://brew.sh)
- A **Groq API key** — free to generate at [console.groq.com/keys](https://console.groq.com/keys). This is the online brain.
- **Ollama** installed with `qwen2.5:7b` pulled (you have this) — the offline brain. No key needed.

> Note on the brain: there's **no Anthropic/OpenAI key** in this project. Online reasoning goes through Groq (free tier, very fast); when you're offline it falls back to Ollama running locally. Both speak the same OpenAI-compatible API, so the code is identical either way — only the base URL and model name change.

## 1. System packages

```bash
brew install python@3.12 ffmpeg whisper-cpp portaudio
```

- `whisper-cpp` — speech-to-text, Metal-accelerated on M1.
- `ffmpeg` — audio recording/conversion.
- `portaudio` — mic access for Python audio libraries.

## 2. Python environment

```bash
cd jarvis
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

## 3. Python packages

```bash
pip install \
  groq \                # online brain (Groq, OpenAI-compatible)
  ollama \              # offline brain (local fallback)
  openwakeword \        # wake word detection
  sounddevice \         # mic capture + audio playback
  numpy \
  silero-vad \          # know when you've stopped speaking (bundled w/ openwakeword too)
  kokoro-mlx \          # TTS, Apple-Silicon-native (MLX, no PyTorch)
  python-dotenv \       # load secrets from .env
  requests \            # calling job-copilot + data APIs
  pyyaml                # routine / progress files
```

> Both `groq` and `ollama` expose OpenAI-style chat + tool calling. If you prefer a single client, you can instead `pip install openai` and point its `base_url` at Groq (`https://api.groq.com/openai/v1`) or Ollama (`http://localhost:11434/v1`) — same code, swap the URL. The `groq` SDK is just a thin, convenient wrapper.

> `kokoro-mlx` requires Apple Silicon and MLX 0.31+. It downloads the Kokoro-82M weights (~327MB) from HuggingFace on first use, then runs fully offline. If you prefer the cross-platform route, swap in `kokoro-onnx` instead — same model, ONNX runtime.

## 4. Whisper model

```bash
mkdir -p ~/.local/share/whisper-models
curl -L -o ~/.local/share/whisper-models/ggml-base.en.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
```

`base.en` is the sweet spot on an M1 Air. If transcription feels slow, drop to `ggml-tiny.en.bin`; if it misses words, step up to `ggml-small.en.bin`.

## 5. Secrets

Create `jarvis/.env` (git-ignored — never commit it):

```
GROQ_API_KEY=gsk_...
# Ollama needs no key.
# Added later: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_NUMBER
```

And a `.gitignore` at the project root:

```
.venv/
.env
__pycache__/
*.pyc
data/
```

## 6. Pick your models

- **Online (Groq):** a solid tool-use default is `llama-3.3-70b-versatile`. For more capability, `openai/gpt-oss-120b`. Model IDs on Groq rotate — check the live list with `curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models` and pin whatever's current.
- **Offline (Ollama):** `qwen2.5:7b` (already pulled). It supports tool calling, so dispatch works offline too — just less capably than the 70B on Groq.

## 7. Wake word model

openWakeWord ships pre-trained models including a "hey jarvis" trigger — no training needed to start. It'll download on first run.

## 8. Full Disk Access (for device-data capabilities)

Several capabilities read Apple's protected local databases — expense SMS (`chat.db`), Screen Time (`knowledgeC.db`), and Messages. macOS blocks these unless the running process has **Full Disk Access**:

- System Settings → Privacy & Security → **Full Disk Access** → add **Terminal.app** (and later, for the auto-start daemon, `/bin/bash`).
- Relaunch the terminal after granting.
- Notes and Reminders instead use **Automation** permission (a prompt appears on first use) rather than Full Disk Access.

For iPhone data to appear on the Mac, make sure iCloud sync is on for the relevant service: **Messages** (Text Message Forwarding, for expense SMS), **Notes**, **Reminders**, and **Screen Time** (Share Across Devices). All are one-time toggles.

> Grant these only to tools you trust — Full Disk Access is powerful. It's what lets Jarvis see your local data; it's also why that data can stay entirely on-device instead of going to some cloud service.

## Verify it all works

```bash
source .venv/bin/activate
python -c "import groq, ollama, openwakeword, sounddevice, numpy; print('core ok')"
whisper-cli --help >/dev/null 2>&1 && echo "whisper ok"
python -c "from kokoro_mlx import KokoroTTS; print('kokoro ok')"
python -c "from groq import Groq; Groq().models.list(); print('groq key ok')"
ollama list | grep qwen2.5 && echo "offline brain ok"
```

If those all print OK, you're ready for Phase 1.

## Disk & memory footprint

- Whisper base.en: ~140MB · Kokoro: ~327MB · openWakeWord: ~50MB · qwen2.5:7b: ~4.7GB (already there).
- The Groq brain is remote, so it costs **no local RAM** when online — a nice win on an 8GB Air. Only the offline Ollama path loads a big model locally.
- Resident RAM when the daemon runs warm (online mode): roughly 1–1.5GB on top of the OS.
