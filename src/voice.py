"""Voice — engine-agnostic, warm, streaming, live-controllable playback.

Reads the mutable STATE fresh every sentence, so "talk softly" / "go deeper" /
"switch to my voice" take effect mid-conversation. Streams sentence-by-sentence
to hide synthesis latency. Engine is swappable via JARVIS_TTS_ENGINE.
"""
import importlib
import os
import queue
import re
import threading

import numpy as np
import sounddevice as sd
from pedalboard import Pedalboard, PitchShift

from lang import detect_lang
from voice_state import STATE

SENT = re.compile(r"(?<=[.!?।])\s+")   # includes the Hindi danda ।


def _normalize_for_speech(text: str) -> str:
    """Make model text sound right out loud. LLMs write '6 000 km' (thin spaces),
    units, symbols — Kokoro reads those literally ('six zero zero zero k m')."""
    # thin/nbsp spaces inside numbers -> joined digits (6 000 -> 6000)
    text = re.sub(r"(\d)[    ](?=\d{3}\b)", r"\1", text)
    # decimals: '7.5' must be 'seven point five', not 'seven five'
    text = re.sub(r"(\d)\.(\d)", r"\1 point \2", text)
    # units & symbols -> words
    text = re.sub(r"\bkm\b", "kilometres", text)
    text = re.sub(r"(\d)\s*°\s*C\b", r"\1 degrees", text)
    text = text.replace("₹", " rupees ").replace("%", " percent")
    # dashes and markdown leftovers read badly
    text = text.replace("–", ", ").replace("—", ", ").replace("*", "")
    return re.sub(r"\s{2,}", " ", text)

# Pick the engine adapter. Kokoro is the safe default; chatterbox is opt-in.
_ENGINE_NAME = os.getenv("JARVIS_TTS_ENGINE", "kokoro").lower()
_engine = importlib.import_module(f"engine_{_ENGINE_NAME}")
synth = _engine.synth


class Voice:
    """Two-stage pipeline: a synth thread renders sentence N+1 while a play thread
    plays sentence N — gapless, non-blocking say(), and interruptible via stop()."""

    def __init__(self):
        self._text_q: queue.Queue = queue.Queue()    # sentences to synthesize
        self._audio_q: queue.Queue = queue.Queue()   # (audio, sr) ready to play
        self._stop = False
        self._synthing = False
        self._playing = False
        threading.Thread(target=self._synth_worker, daemon=True).start()
        threading.Thread(target=self._play_worker, daemon=True).start()

    def _synth(self, sentence: str):
        lang = detect_lang(sentence) if STATE.language == "auto" else STATE.language
        audio, sr = synth(                       # engine call, reads live STATE
            text=sentence, ref=STATE.voice_ref, language=lang,
            emotion=STATE.emotion, intensity=STATE.intensity, rate=STATE.rate,
        )
        if STATE.pitch_semitones:                # DSP pitch shim on top of engine
            board = Pedalboard([PitchShift(semitones=STATE.pitch_semitones)])
            audio = board(np.asarray(audio, dtype=np.float32), sr)
        return audio, sr

    def _synth_worker(self) -> None:
        while True:
            sentence = self._text_q.get()
            try:
                if not self._stop:
                    self._synthing = True
                    self._audio_q.put(self._synth(sentence))
            except Exception as e:
                # Never let one synth failure kill the voice for good.
                print(f"[voice] synth error: {type(e).__name__}: {e}", flush=True)
            finally:
                self._synthing = False
                self._text_q.task_done()

    def _play_worker(self) -> None:
        import time as _t
        while True:
            audio, sr = self._audio_q.get()
            try:
                if not self._stop:
                    self._playing = True
                    sd.play(audio, sr)
                    # WATCHDOG instead of sd.wait(): wait() can block forever if
                    # CoreAudio wedges (e.g. right after Chromium touched the audio
                    # device). We know exactly how long the clip is — never wait
                    # longer. Also makes stop() responsive mid-sentence.
                    deadline = _t.time() + len(audio) / float(sr) + 0.6
                    while _t.time() < deadline and not self._stop:
                        _t.sleep(0.05)
                    sd.stop()
            except Exception as e:
                print(f"[voice] playback error: {type(e).__name__}: {e}", flush=True)
            finally:
                self._playing = False
                self._audio_q.task_done()

    def warmup(self) -> None:
        """Pre-load the TTS model (synthesize + discard) so the first real reply
        doesn't pay the cold-load. Call at startup and when waking from deep sleep."""
        try:
            self._synth("Ready.")
        except Exception:
            pass

    def unload(self) -> None:
        """Release the TTS model from RAM (deep sleep). warmup() reloads it."""
        if hasattr(_engine, "unload"):
            _engine.unload()

    def say(self, text: str) -> None:
        """Queue text to speak. The FIRST sentence goes in alone so audio starts
        fast (~0.3s synth); the remainder follows as one piece — still gapless,
        because synth outruns playback and chunk two is ready before one ends."""
        self._stop = False
        text = _normalize_for_speech(text.strip())
        if not text:
            return
        for part in SENT.split(text, maxsplit=1):
            if part.strip():
                self._text_q.put(part.strip())

    def is_speaking(self) -> bool:
        return (self._synthing or self._playing
                or not self._text_q.empty() or not self._audio_q.empty())

    def stop(self) -> None:
        """Interrupt now: halt playback and drop everything still queued."""
        self._stop = True
        try:
            sd.stop()
        except Exception:
            pass
        for q in (self._text_q, self._audio_q):
            while not q.empty():
                try:
                    q.get_nowait(); q.task_done()
                except queue.Empty:
                    break

    def wait(self, timeout: float = 60.0) -> None:
        """Block until speech finishes — but NEVER longer than `timeout`. A wedged
        synth/audio call may cost one reply; it may not freeze the daemon."""
        import time as _t
        deadline = _t.time() + timeout
        while self.is_speaking() and _t.time() < deadline:
            _t.sleep(0.05)
        if self.is_speaking():
            print("[voice] wait() timed out — dropping stuck speech", flush=True)
            self.stop()


def engine_name() -> str:
    return _ENGINE_NAME
