# Setup, running & permissions

## One-time install

```bash
# System (Homebrew)
brew install python@3.12 ffmpeg whisper-cpp portaudio espeak-ng corelocationcli

# Python venv
cd jarvis && python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # openai, kokoro, sounddevice, soundfile,
                                          # pedalboard, openwakeword, onnxruntime,
                                          # silero-vad, playwright, numpy, python-dotenv
playwright install chromium

# Models
#   whisper: ~/.local/share/whisper-models/ggml-small.en.bin (and/or base.en)
#   Kokoro:  auto-downloads from HuggingFace on first use (~330MB, cached)
#   Ollama offline brain:  ollama pull qwen2.5:7b
#   Vision (optional):     ollama pull qwen2.5vl:3b
```

## Secrets (`.env`, git-ignored)

```
GROQ_API_KEY=gsk_...        # free at console.groq.com/keys — the online brain
```

## macOS permissions (grant once)

| Permission | Needed for | Where |
|---|---|---|
| **Microphone** | listening | Privacy & Security → Microphone |
| **Screen Recording** | `see_screen` | Privacy & Security → Screen Recording |
| **Automation** | app control, notes, media (AppleScript) | prompts on first use |
| **Full Disk Access** | (future) reading chat.db / knowledgeC.db | Privacy & Security → Full Disk Access |
| **Location Services** | `get_location` GPS (CoreLocationCLI) — finicky, see ISSUES | Privacy & Security → Location Services |

## Running

```bash
source .venv/bin/activate
python src/listen.py            # hands-free: "Hey Jarvis", then talk
python src/listen.py friday     # start as Friday
```

### Login daemon (always-on)
```bash
bash scripts/install-daemon.sh     # runs at login, models pre-warmed, restarts on crash
bash scripts/uninstall-daemon.sh   # stop + remove
tail -f logs/daemon.out.log        # watch it
```
Note: don't run `listen.py` manually while the daemon is running — they fight for the mic.

## Environment variables

| Var | Default | Effect |
|---|---|---|
| `GROQ_API_KEY` | — | online brain (Groq); absent → Ollama offline |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | online model |
| `OLLAMA_MODEL` | `qwen2.5:7b` | offline model |
| `JARVIS_BARGE_IN` | `off` | `off` (best audio) / `wake` / `voice` (headphones) |
| `JARVIS_FOLLOWUP` | `1` | conversation mode (keep talking, no repeat wake) |
| `JARVIS_SLEEP_AFTER` | `300` | idle seconds → unload voice model (free RAM); 0 disables |
| `JARVIS_WAKE_THRESHOLD` | `0.5` | lower = triggers from farther (more false wakes) |
| `WHISPER_MODEL` | small.en if present | STT model path |
| `JARVIS_TTS_ENGINE` | `kokoro` | TTS engine adapter |
| `JARVIS_VISION_MODEL` | `qwen2.5vl:3b` | Ollama vision model for `see_screen` |
| `JARVIS_BROWSER_HEADLESS` | `0` | `1` = invisible browser (gets more captchas) |
