"""Conduct the voice mid-conversation. Each function mutates the live STATE;
name/voice changes persist via memory.remember so they survive restarts.

Registered as tools so Phase 3 dispatch can route natural speech to them
("talk softer" -> set_emotion("soft")). Until then they're callable directly.
"""
import os
import re

import memory
from brain import tool
from voice_state import EMOTION_REGISTER, STATE

# A valid voice is either a Kokoro voice id (e.g. bm_george) or a clip in the
# registry — guards against a weak model shoving garbage into set_voice.
_KOKORO_VOICE = re.compile(r"^[abhef][mf]_[a-z]+$")
_VOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                           "data", "voices")


def _valid_voice(name: str) -> bool:
    return bool(_KOKORO_VOICE.match(name)) or os.path.exists(
        os.path.join(_VOICES_DIR, name if name.endswith(".wav") else name + ".wav"))


@tool({"name": "set_voice",
       "description": "Switch to a different voice by name (voice id or cloned-clip name).",
       "parameters": {"type": "object",
           "properties": {"name": {"type": "string"}}, "required": ["name"]}})
def set_voice(name: str):
    if not _valid_voice(name):
        return {"error": f"unknown voice '{name}'", "voice": STATE.voice_ref}
    STATE.voice_ref = name
    memory.remember("voice_ref", name)
    return {"voice": name}


@tool({"name": "rename_self",
       "description": "Change the assistant's name/identity.",
       "parameters": {"type": "object",
           "properties": {"name": {"type": "string"}}, "required": ["name"]}})
def rename_self(name: str):
    STATE.name = name
    memory.remember("assistant_name", name)   # persists across restarts
    return {"name": name}


@tool({"name": "set_emotion",
       "description": "Set emotional delivery: neutral, soft, seductive, excited, angry, sad.",
       "parameters": {"type": "object",
           "properties": {"emotion": {"type": "string"}, "intensity": {"type": "number"}},
           "required": ["emotion"]}})
def set_emotion(emotion: str, intensity: float | None = None):
    emotion = emotion.lower().strip()
    if emotion not in EMOTION_REGISTER:
        return {"error": f"unknown emotion '{emotion}'", "emotion": STATE.emotion}
    STATE.emotion = emotion
    if intensity is not None:
        STATE.intensity = max(0.0, min(1.5, intensity))
    return {"emotion": emotion, "intensity": STATE.intensity}


@tool({"name": "set_pitch",
       "description": "Shift pitch. Negative = deeper, positive = higher. Semitones.",
       "parameters": {"type": "object",
           "properties": {"semitones": {"type": "number"}}, "required": ["semitones"]}})
def set_pitch(semitones: float):
    STATE.pitch_semitones = max(-8, min(8, semitones))
    return {"pitch": STATE.pitch_semitones}


@tool({"name": "set_rate",
       "description": "Speaking rate. 0.8 slow … 1.2 fast.",
       "parameters": {"type": "object",
           "properties": {"rate": {"type": "number"}}, "required": ["rate"]}})
def set_rate(rate: float):
    STATE.rate = max(0.6, min(1.6, rate))
    return {"rate": STATE.rate}
