"""Per-sentence language detection for one-voice-every-language routing.

Cheap script-based detection — extend with more Unicode ranges as you add
languages. For mixed Hinglish, split on script runs before calling synth.
"""
import re

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def detect_lang(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    hindi = sum(bool(DEVANAGARI.match(c)) for c in letters) / len(letters)
    return "hi" if hindi > 0.3 else "en"
