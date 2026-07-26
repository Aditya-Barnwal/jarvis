"""Live, mutable voice state — the single source of truth the daemon holds.

Voice-command tools (tools/voice_control.py) mutate this; Voice.say() reads it
fresh every sentence, so changes take effect mid-conversation. Name and voice_ref
persist across restarts via the memory store (see load_persisted).
"""
from dataclasses import dataclass


@dataclass
class VoiceState:
    name: str = "Jarvis"           # spoken identity; rename on command
    voice_ref: str = "bm_george"   # engine-interpreted voice id / clip name
    language: str = "auto"         # 'auto' detects per sentence; or force 'en','hi'
    # expressive controls:
    emotion: str = "neutral"       # neutral|angry|soft|excited|seductive|sad|...
    intensity: float = 0.5         # 0.0–1.0+  (cloning-engine 'exaggeration' dial)
    pitch_semitones: float = 0.0   # DSP pitch shift; - = deeper, + = higher
    rate: float = 1.0              # speaking rate (0.8 slower … 1.2 faster)


STATE = VoiceState()   # single source of truth, held in the daemon


def load_persisted() -> None:
    """Restore name/voice/emotion set in a previous session, if any."""
    try:
        import memory
    except Exception:
        return
    STATE.name = memory.recall("assistant_name", STATE.name)
    STATE.voice_ref = memory.recall("voice_ref", STATE.voice_ref)


# --- how each emotion colors the WORDS (fed into the brain system prompt) ---
EMOTION_REGISTER = {
    "neutral": "",
    "angry": "You are irritated: clipped, blunt, terse sentences. No pleasantries.",
    "soft": "Speak gently and reassuringly, in slower, softer phrasing.",
    "seductive": "Speak low and unhurried, warm and intimate word choice.",
    "excited": "You are enthusiastic and energetic, but still no exclamation marks.",
    "sad": "Speak subdued and quiet, with muted, heavier phrasing.",
}


def emotion_register(emotion: str) -> str:
    return EMOTION_REGISTER.get(emotion, "")
