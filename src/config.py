"""Central config for Jarvis. Reads .env, picks models/voices.

One place to change model names, voices, and thresholds so the rest of the
code never hardcodes them. See SETUP.md for how to get a GROQ_API_KEY.
"""
import os

try:
    from dotenv import load_dotenv
    # Load jarvis/.env regardless of where the process was launched from.
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ModuleNotFoundError:
    # python-dotenv not installed yet — env vars from the shell still work.
    pass

# --- Brain: online (Groq) vs offline (Ollama) -----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# gpt-oss-20b does clean, consistent tool-calling on Groq; llama-3.3-70b is
# flaky (emits malformed <function=…> text and misses tool calls). Both free.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
# Auto-escalation target for hard asks (teach/explain/analyze/long). Also free.
GROQ_MODEL_SMART = os.getenv("GROQ_MODEL_SMART", "openai/gpt-oss-120b")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
# qwen2.5:7b is the offline default — it routes tool-calls at 95% vs llama3.2:3b's
# 29% (see tests/routing_test.py), with zero false-positives on conversation.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# --- Voice ----------------------------------------------------------------
# Kokoro language: "b" = British English (Jarvis/Friday vibe), "a" = American.
# Per-voice IDs and speeds live on each Persona (see personas.py).
KOKORO_LANG = os.getenv("KOKORO_LANG", "b")

# Fallback system prompt if no persona is supplied. Personas override this.
SYSTEM_PROMPT = (
    "You are Jarvis, a concise, warm personal assistant. "
    "Keep replies short and speakable — a sentence or two, no markdown, no lists."
)


def has_groq_key() -> bool:
    return bool(GROQ_API_KEY) and GROQ_API_KEY != "gsk_..."
