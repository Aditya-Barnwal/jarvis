"""Chatterbox Multilingual V3 engine adapter — cloning + emotion (DORMANT).

Not active by default: chatterbox-tts pins torch==2.6 / numpy<2, which conflicts
with the working Kokoro stack, and 8GB RAM is tight to hold it alongside Ollama.
Install it in an ISOLATED venv so it can't corrupt the main one:

    python3.12 -m venv .venv-chatterbox
    ./.venv-chatterbox/bin/pip install chatterbox-tts

Then enable via env:  JARVIS_TTS_ENGINE=chatterbox
(and run the voice worker from that venv). Same synth() signature as
engine_kokoro, so nothing else in the app changes — the whole point of the
adapter layer. Reference clips live in data/voices/ (own/consented/licensed only).
"""
_model = None

# Map friendly emotions to Chatterbox's exaggeration dial.
_EMO = {"neutral": 0.5, "soft": 0.3, "seductive": 0.4, "sad": 0.4,
        "excited": 0.8, "angry": 0.9}

_LANG_ID = {"en": "en", "hi": "hi"}   # extend as you add languages


def _get_model():
    global _model
    if _model is None:
        from chatterbox.tts import ChatterboxMultilingualTTS
        _model = ChatterboxMultilingualTTS.from_pretrained(device="mps")  # warm
    return _model


def synth(text, ref, language, emotion, intensity, rate):
    import numpy as np
    model = _get_model()
    exaggeration = _EMO.get(emotion, intensity)
    lang_id = _LANG_ID.get(language, "en")
    ref_path = f"data/voices/{ref if ref.endswith('.wav') else ref + '.wav'}"
    wav = model.generate(text, audio_prompt_path=ref_path, language_id=lang_id,
                         exaggeration=exaggeration, cfg_weight=0.5)
    audio = wav.squeeze().cpu().numpy() if hasattr(wav, "cpu") else np.asarray(wav)
    return audio.astype("float32"), 24000
