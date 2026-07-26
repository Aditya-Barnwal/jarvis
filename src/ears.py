"""Ears — mic capture + whisper.cpp transcription (Phase 1, Milestone 2).

Press-to-talk: press Enter to start, Enter again to stop; the clip is
transcribed locally by whisper.cpp (Metal-accelerated, fully offline).
Milestone 3 swaps the Enter gate for wake word + VAD.
"""
import os
import queue
import subprocess
import tempfile

import numpy as np
import soundfile as sf

SR = 16000  # whisper.cpp wants 16 kHz mono
_MODELS = os.path.expanduser("~/.local/share/whisper-models")


def _default_model() -> str:
    # Prefer small.en (more accurate in noise / with earphones) if present.
    small = os.path.join(_MODELS, "ggml-small.en.bin")
    return small if os.path.exists(small) else os.path.join(_MODELS, "ggml-base.en.bin")


MODEL = os.getenv("WHISPER_MODEL", _default_model())
_WAV = os.path.join(tempfile.gettempdir(), "jarvis_in.wav")


def record_until_enter() -> np.ndarray:
    """Record from the mic between two Enter presses. Returns mono float32."""
    import sounddevice as sd

    q: queue.Queue = queue.Queue()

    def cb(indata, frames, time_info, status):
        q.put(indata.copy())

    input("🎙️  Press Enter to speak…")
    with sd.InputStream(samplerate=SR, channels=1, dtype="float32", callback=cb):
        input("   recording — press Enter to stop…")

    frames = []
    while not q.empty():
        frames.append(q.get())
    return np.concatenate(frames).flatten() if frames else np.zeros(0, dtype="float32")


def transcribe(audio: np.ndarray, hint: str = "") -> str:
    """Transcribe a mono float32 clip with whisper.cpp. `hint` (e.g. the previous
    exchange) biases decoding, so corrections like a repeated place name are
    heard as the same word instead of drifting ('Pind' -> 'wind')."""
    if audio.size < SR // 2:      # < 0.5s — treat as nothing said
        return ""
    sf.write(_WAV, audio, SR, subtype="PCM_16")
    base = _WAV[:-4]              # whisper-cli adds .txt to the -of base
    cmd = ["whisper-cli", "-m", MODEL, "-f", _WAV, "-otxt", "-of", base, "-nt", "-np"]
    if hint:
        cmd += ["--prompt", hint[:200]]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        with open(base + ".txt") as f:
            return f.read().strip()
    except Exception:
        # STT failure must never crash the daemon — empty text reads as "didn't catch".
        return ""


# --- Milestone 3: hands-free wake word + VAD --------------------------------
WAKE_CHUNK = 1280   # 80ms @ 16k — openWakeWord's frame size
VAD_CHUNK = 512     # 32ms @ 16k — Silero VAD's frame size


class Ears:
    """Hands-free listening: openWakeWord detects 'hey jarvis', then Silero VAD
    records until you stop talking. Heavy deps are imported lazily here so the
    press-to-talk path (record_until_enter) doesn't require them."""

    def __init__(self, wakeword: str = "hey_jarvis", wake_threshold: float = 0.5,
                 barge_rms: float = 0.08):
        import collections
        import threading

        from openwakeword.model import Model
        from silero_vad import load_silero_vad

        self.wakeword = wakeword
        self.wake_threshold = wake_threshold
        self.barge_rms = barge_rms   # loudness gate for voice-mode barge-in
        self.oww = Model(wakeword_models=[wakeword], inference_framework="onnx")
        self.vad_model = load_silero_vad()
        # ONE callback-fed stream for the whole session. pause/resume is a
        # SOFTWARE gate (discard frames) — never stop/close the device mid-session:
        # PortAudio close wedges on this machine, and a wedged close poisons the
        # next open (the stall saga). No state transitions = nothing to wedge.
        self._stream = None
        self._buf = collections.deque()
        self._buf_len = 0                       # samples currently buffered
        self._buf_lock = threading.Lock()
        self._gate = True                       # False = discard incoming audio

    def _cb(self, indata, frames, time_info, status):
        if self._gate:
            with self._buf_lock:
                self._buf.append(indata.copy().reshape(-1))
                self._buf_len += frames
                while self._buf_len > SR * 30:  # cap backlog at 30s
                    old = self._buf.popleft()
                    self._buf_len -= len(old)

    def wait_for_wake(self) -> float:
        """Block until the wake word fires; returns the detection score."""
        import sounddevice as sd

        self.oww.reset()
        with sd.InputStream(samplerate=SR, channels=1, dtype="int16",
                            blocksize=WAKE_CHUNK) as stream:
            while True:
                frame, _ = stream.read(WAKE_CHUNK)
                score = self.oww.predict(frame.flatten())[self.wakeword]
                if score > self.wake_threshold:
                    return float(score)

    def start(self, prime_frames: int = 12) -> None:
        """Open the callback-fed mic stream (ONCE per session) and warm the wake
        model with `prime_frames` frames of real audio (80ms each)."""
        import sounddevice as sd

        self._flush()
        self._gate = True
        self._stream = sd.InputStream(samplerate=SR, channels=1, dtype="int16",
                                      blocksize=VAD_CHUNK, callback=self._cb)
        self._stream.start()
        self.oww.reset()
        for _ in range(prime_frames):
            self.oww.predict(self._read(WAKE_CHUNK).flatten())

    def _flush(self) -> None:
        with self._buf_lock:
            self._buf.clear()
            self._buf_len = 0

    def close(self) -> None:
        """Close the mic — with a hard timeout. PortAudio's stop/close can wedge
        (seen after heavy Chromium activity); if it does, ABANDON the stream object
        rather than freezing the daemon. A leaked handle beats a dead assistant."""
        if self._stream is None:
            return
        import threading

        stream, self._stream = self._stream, None

        def _do_close():
            try:
                stream.stop(); stream.close()
            except Exception:
                pass

        t = threading.Thread(target=_do_close, daemon=True)
        t.start()
        t.join(timeout=3.0)
        if t.is_alive():
            print("[ears] mic close wedged — abandoned handle, continuing", flush=True)

    def _read(self, frames: int) -> np.ndarray:
        """Assemble `frames` samples from the callback ring buffer. If the stream
        stops delivering audio (device died / BT disconnect), recreate it."""
        import time

        chunks, have = [], 0
        deadline = time.time() + 8.0
        while have < frames:
            with self._buf_lock:
                while self._buf and have < frames:
                    c = self._buf.popleft()
                    self._buf_len -= len(c)
                    chunks.append(c)
                    have += len(c)
            if have < frames:
                if time.time() > deadline:
                    print("[ears] no audio arriving — recreating input stream…", flush=True)
                    self.close()
                    time.sleep(1.0)
                    try:
                        self.start(prime_frames=1)
                    except Exception as e:
                        print(f"[ears] reopen failed ({type(e).__name__}); retrying…",
                              flush=True)
                    deadline = time.time() + 8.0
                time.sleep(0.01)
        data = np.concatenate(chunks)
        if len(data) > frames:                     # push the remainder back
            with self._buf_lock:
                self._buf.appendleft(data[frames:])
                self._buf_len += len(data) - frames
            data = data[:frames]
        return data

    def pause(self) -> None:
        """Software gate OFF while Jarvis speaks: incoming audio is discarded so he
        doesn't hear himself. The device stays open — closing it per turn is what
        wedged CoreAudio and caused the stalls."""
        self._gate = False
        self._flush()

    def resume(self) -> None:
        """Instant: re-enable the gate, drop anything stale, re-arm the wake model."""
        self._flush()
        self._gate = True
        self.oww.reset()

    def poll_wake(self, seconds: float) -> bool:
        """Listen for the wake word for up to `seconds`. True if woken, False if it
        timed out (lets the caller check idle time and deep-sleep between polls).
        Keeps the wake model warm by reading continuously."""
        import time

        t0 = time.time()
        while time.time() - t0 < seconds:
            frame = self._read(WAKE_CHUNK)
            if self.oww.predict(frame.flatten())[self.wakeword] > self.wake_threshold:
                return True
        return False

    def capture(self, skip_wake: bool = False, on_wake=None, max_sec: float = 15,
                start_timeout_sec: float = 6, min_silence_ms: int = 700) -> np.ndarray:
        """Wait for the wake word (unless skip_wake, e.g. right after a barge-in),
        then record with VAD on the persistent stream. Returns mono float32."""
        import time

        import torch
        from silero_vad import VADIterator

        if not skip_wake:
            while True:
                frame = self._read(WAKE_CHUNK)
                if self.oww.predict(frame.flatten())[self.wakeword] > self.wake_threshold:
                    break
            if on_wake:
                on_wake()

        vad = VADIterator(self.vad_model, sampling_rate=SR,
                          min_silence_duration_ms=min_silence_ms)
        audio, started, t0 = [], False, time.time()
        while True:
            block = self._read(VAD_CHUNK)
            chunk = block.flatten().astype("float32") / 32768.0
            audio.append(chunk)
            flags = vad(torch.from_numpy(chunk))
            if flags:
                if "start" in flags:
                    started = True
                if "end" in flags and started:
                    break
            if not started and time.time() - t0 > start_timeout_sec:
                audio = []
                break
            if time.time() - t0 > max_sec:
                break
        vad.reset_states()
        return np.concatenate(audio) if audio else np.zeros(0, dtype="float32")

    def monitor_while_speaking(self, voice, mode: str = "wake") -> bool:
        """Watch the mic WHILE Jarvis is speaking and interrupt him if the user
        barges in. Returns True if interrupted (voice.stop already called), False
        if he finished normally.

        mode='wake'  (speaker-safe): say 'Hey Jarvis' to cut him off. Echo-safe
                     because he never utters his own wake word.
        mode='voice' (headphones/AEC): any speech over a loudness gate interrupts.
                     On laptop speakers this can self-trigger on his own echo.
        mode='off' : no barge-in; just wait for him to finish."""
        if mode == "off":
            voice.wait()
            return False
        if mode == "voice":
            import torch
            from silero_vad import VADIterator
            vad = VADIterator(self.vad_model, sampling_rate=SR, min_silence_duration_ms=200)
            try:
                while voice.is_speaking():
                    block = self._read(VAD_CHUNK)
                    chunk = block.flatten().astype("float32") / 32768.0
                    rms = float(np.sqrt(np.mean(chunk * chunk)))
                    flags = vad(torch.from_numpy(chunk))
                    if flags and "start" in flags and rms > self.barge_rms:
                        voice.stop(); return True
            finally:
                vad.reset_states()
            return False
        # default: wake-word barge-in.
        # Clear the wake model first — it still holds the 'hey jarvis' that
        # started THIS turn; without this it re-fires instantly (false cut-in
        # that also kills playback). After reset it needs a fresh 'Hey Jarvis'.
        self.oww.reset()
        while voice.is_speaking():
            frame = self._read(WAKE_CHUNK)
            if self.oww.predict(frame.flatten())[self.wakeword] > self.wake_threshold:
                voice.stop(); return True
        return False

    def record_until_silence(self, max_sec: float = 15, start_timeout_sec: float = 4,
                             min_silence_ms: int = 700) -> np.ndarray:
        """Record from wake until Silero VAD sees a trailing silence. Returns
        empty if the user never actually started speaking (start_timeout)."""
        import time

        import sounddevice as sd
        import torch
        from silero_vad import VADIterator

        vad = VADIterator(self.vad_model, sampling_rate=SR,
                          min_silence_duration_ms=min_silence_ms)
        audio, started, t0 = [], False, time.time()
        with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                            blocksize=VAD_CHUNK) as stream:
            while True:
                block, _ = stream.read(VAD_CHUNK)
                chunk = block.flatten()
                audio.append(chunk)
                flags = vad(torch.from_numpy(chunk))
                if flags:
                    if "start" in flags:
                        started = True
                    if "end" in flags and started:
                        break
                if not started and time.time() - t0 > start_timeout_sec:
                    vad.reset_states()
                    return np.zeros(0, dtype="float32")
                if time.time() - t0 > max_sec:
                    break
        vad.reset_states()
        return np.concatenate(audio) if audio else np.zeros(0, dtype="float32")
