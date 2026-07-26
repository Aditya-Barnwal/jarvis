"""Mic + wake-word + VAD diagnostic. Run this, follow the prompts, paste output.

    source .venv/bin/activate
    python src/miccheck.py

Tells us, with real numbers, which link is failing:
  - mic RMS ~0        -> mic isn't capturing (permission / wrong device)
  - wake peak < 0.5   -> threshold too high for your voice/mic (we lower it)
  - VAD sees nothing  -> speech not registering (level / VAD sensitivity)
  - capture ok, text empty -> whisper/STT issue
"""
import time

import numpy as np
import sounddevice as sd

import ears

SR, CHUNK = 16000, 1280


def rms(int16frame):
    f = int16frame.astype("float32") / 32768.0
    return float(np.sqrt(np.mean(f * f)))


def main():
    print("=== audio devices ===")
    print(sd.query_devices())
    try:
        din = sd.query_devices(kind="input")
        print(f"default input: {din['name']}  (native SR {din['default_samplerate']})")
    except Exception as e:
        print("no default input device!", e)

    print("\nLoading wake word + VAD…")
    listener = ears.Ears(wakeword="hey_jarvis")

    # Phase A — live wake scoring
    print('\n=== PHASE A: say "Hey Jarvis" a few times over the next 8 seconds ===')
    peak_score = peak_rms = 0.0
    listener.oww.reset()
    with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=CHUNK) as s:
        t0 = time.time()
        while time.time() - t0 < 8:
            frame, _ = s.read(CHUNK)
            f = frame.flatten()
            r = rms(f)
            sc = listener.oww.predict(f)["hey_jarvis"]
            peak_rms = max(peak_rms, r)
            peak_score = max(peak_score, sc)
            if sc > 0.1:
                print(f"   wake score {sc:.2f}   (mic rms {r:.3f})")
    print(f">>> PHASE A: peak wake score = {peak_score:.2f}   peak mic rms = {peak_rms:.3f}")
    print("    (rms near 0 = mic silent; wake >0.5 = would trigger)")

    # Phase B — real VAD capture + transcribe
    print('\n=== PHASE B: say a full sentence now (e.g. "what time is it") ===')
    audio = listener.record_until_silence()
    secs = len(audio) / SR
    arms = float(np.sqrt(np.mean(audio * audio))) if audio.size else 0.0
    print(f">>> captured {secs:.1f}s of audio  (rms {arms:.3f})")
    if audio.size:
        text = ears.transcribe(audio)
        print(f">>> transcription: {text!r}")
    else:
        print(">>> VAD captured nothing — speech start never detected within timeout")


if __name__ == "__main__":
    main()
