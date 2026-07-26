"""Kokoro engine adapter — the fast, tiny, zero-risk default.

Implements the common synth(text, ref, language, emotion, intensity, rate) ->
(audio, sr) contract. Kokoro can't clone and uses a *per-language* voice, so:
  - `ref` is interpreted as a Kokoro voice id (e.g. 'bm_george').
  - `language` selects the pipeline; for non-English we map to a same-gender
    Kokoro voice of that language (timbre shifts — true one-voice-all-languages
    is the cloning engine's job; see engine_chatterbox.py).
  - `emotion`/`intensity` have no acoustic dial here; expression comes from the
    pitch/rate DSP in voice.py plus the brain rewriting the words.
"""
import numpy as np

# Kokoro lang_code + a default voice per detected language.
_LANG = {
    "en": ("b", "bm_george"),   # British English
    "hi": ("h", "hm_omega"),    # Hindi (needs misaki[hi]; falls back if absent)
}
_pipes: dict[str, "object"] = {}   # lang_code -> warm KPipeline (loaded once each)


import threading

_load_lock = threading.Lock()


def _pipe(lang_code: str):
    # Lock: warmup thread + synth worker must never double-load the model
    # (two simultaneous KPipeline loads on 8GB = swap storm).
    with _load_lock:
        if lang_code not in _pipes:
            from kokoro import KPipeline
            _pipes[lang_code] = KPipeline(lang_code=lang_code)
        return _pipes[lang_code]


def unload():
    """Free the Kokoro model(s) from RAM (deep sleep). Reloads lazily on next use."""
    import gc
    _pipes.clear()
    gc.collect()


_blends: dict = {}   # "bm_george:0.7,bm_lewis:0.3" -> blended voice tensor


def _resolve_voice(pipe, ref: str):
    """Support blended voices ('bm_george:0.7,bm_lewis:0.3') — a weighted average
    of voice embeddings gives a deeper, less synthetic Jarvis. Falls back to the
    first named voice if blending isn't supported by the installed kokoro."""
    if "," not in ref:
        return ref
    if ref in _blends:
        return _blends[ref]
    try:
        import torch
        total, mixed = 0.0, None
        for part in ref.split(","):
            name, _, w = part.strip().partition(":")
            w = float(w or 1.0)
            v = pipe.load_voice(name)
            mixed = v * w if mixed is None else mixed + v * w
            total += w
        _blends[ref] = mixed / total
        return _blends[ref]
    except Exception:
        return ref.split(",")[0].split(":")[0].strip()


def _voice_for(ref: str, lang: str) -> tuple[str, str]:
    lang_code, default_voice = _LANG.get(lang, _LANG["en"])
    # Keep the requested ref only if it belongs to this language's pipeline.
    voice = ref if ref and ref[0] == lang_code else default_voice
    return lang_code, voice


def synth(text, ref, language, emotion, intensity, rate):
    lang = language if language in _LANG else "en"
    lang_code, voice = _voice_for(ref, lang)
    try:
        pipe = _pipe(lang_code)
        voice = _resolve_voice(pipe, voice)
        chunks = [np.asarray(a) for _, _, a in pipe(text, voice=voice, speed=rate)]
    except Exception:
        # Degrade gracefully to English rather than crash the voice loop.
        pipe = _pipe("b")
        chunks = [np.asarray(a) for _, _, a in pipe(text, voice="bm_george", speed=rate)]
    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    return audio, 24000
