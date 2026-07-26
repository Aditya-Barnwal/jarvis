# Decisions

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [docs/build/](docs/build/).

Why each tool was chosen over its alternatives. Kept short — the point is that these were considered, not accidental.

---

## Wake word: openWakeWord (not Porcupine)

- **openWakeWord** — free, open-source, ONNX, no API key, runs many models in real time on tiny hardware. Bundles Silero VAD. Ships a "hey jarvis" model out of the box. Matches the free-and-private principle.
- **Porcupine (Picovoice)** — more polished, trains a custom wake word in seconds, but needs an access key and its free tier has limits.
- **Verdict:** Start on openWakeWord's stock trigger. Switch to Porcupine only if the stock trigger's false-accept rate annoys you. Both swap behind the same `ears.py` interface.

## STT: whisper.cpp with Metal (not cloud, not faster-whisper)

- **whisper.cpp** — Metal-accelerated on M1, fully local, dead simple (`brew install`), the community standard. `base.en` gives ~0.5s transcription on an M1 Air.
- Cloud STT — faster/more accurate, but sends your audio off-device. Violates local-first.
- **Verdict:** whisper.cpp. Privacy + zero cost beats the marginal accuracy gap.

## Brain: Groq online, Ollama offline (no Anthropic/OpenAI key)

This is the deliberate core choice: **no paid proprietary brain**. Both backends are free and both speak the OpenAI-compatible API, so the code is identical — only the base URL + model name change.

- **Groq (online)** — free tier, and *very* fast (LPU inference). Hosts open models (Llama, Qwen, GPT-OSS, DeepSeek-R1 variants). Every model on Groq supports tool use / function calling, which is the backbone of the whole extensibility model. Default: `llama-3.3-70b-versatile`; step up to `openai/gpt-oss-120b` for harder reasoning. (Model IDs rotate — check the live `/models` list.)
- **Ollama (offline)** — `qwen2.5:7b`, already installed, runs fully local. Also supports tool calling, so dispatch still works with no internet — just less capably than the 70B.
- **Why not Anthropic/OpenAI paid APIs?** No need — Groq's free tier covers a personal assistant's volume, and staying key-light keeps the project genuinely free-and-local-first. If Groq is ever down and you're online, any OpenAI-compatible provider is a one-line base-URL swap.
- **Verdict:** Two-tier, both free, one code path. Online = fast + smart, offline = functional.

### Consequence: one tool format everywhere

Because Groq and Ollama both use the OpenAI function-calling schema (`{"type":"function","function":{...}}` → model returns `tool_calls`), the dispatch layer is written **once** and works against either backend. No per-provider tool code. This is a big simplification vs. maintaining separate formats.

## TTS: kokoro-mlx (not ONNX, not Piper, not ElevenLabs)

- **kokoro-mlx** — Apple-Silicon-native (MLX, no PyTorch), gapless streaming, 54 voices, fully on-device. Best quality-per-MB local TTS in 2026 (Kokoro-82M ranked #1 on the TTS Spaces Arena at launch).
- **kokoro-onnx** — same model, ONNX runtime, cross-platform. Fine fallback.
- **Piper** — faster/tinier but audibly more synthetic; original repo archived late 2025.
- **ElevenLabs** — best-sounding, but cloud (privacy cost) and paid.
- **Verdict:** kokoro-mlx. Local, free, natural enough. Voice `am_puck` or `af_heart`.

## Memory: SQLite first, ChromaDB later

- **SQLite** — already in job-copilot, zero new infra, perfect for facts/preferences/summaries.
- **ChromaDB** — adds semantic recall; worth it only once keyword lookup gets weak.
- **Verdict:** Start SQLite. Add Chroma later only if needed.

## Orchestration: one asyncio daemon (not microservices)

- A single long-running process keeps models warm and the mental model simple. It's a personal assistant on one laptop — resist over-engineering.

## Browser: Playwright, self-hosted local (Phase 4)

- Playwright runs locally — no remote-device connector exists (checked). Note: Groq also offers a built-in web-search / "compound" tool that can handle simple "look this up" queries server-side without Playwright — cheaper for quick lookups. Use Groq web search for quick facts, Playwright for real navigation/form-filling.

## Telephony (calls/SMS): Twilio or macOS Continuity (Phase 5)

- **Twilio** — real programmatic calls/SMS, paid, legitimate.
- **macOS Continuity + AppleScript** — route through your paired iPhone, free.
- **Verdict:** Offer both as tools; pick per situation. Detail in [docs/capabilities/calls-and-messaging.md](capabilities/calls-and-messaging.md).
