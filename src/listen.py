"""The Jarvis daemon — hands-free voice assistant (this IS the always-on loop).

Say "Hey Jarvis", then just talk — wake word (openWakeWord) → VAD (Silero) →
whisper.cpp STT → brain (Groq online / Ollama offline) with tool dispatch →
Kokoro voice. Personas: Jarvis (professional) / Friday (personal). Conversation
mode keeps listening between turns; sessions are summarized into long-term
memory; gated actions (install/shell) need a spoken yes and can be ABORTED
mid-flight ("stop" / "abort" while they run).

Run:
    source .venv/bin/activate
    python src/listen.py               # Jarvis
    python src/listen.py friday        # Friday persona
Ctrl-C to stop.  As a login daemon: scripts/install-daemon.sh
"""
import os
import re
import signal
import sys
import threading
import time

import brain
import ears
import memory
import tools
from brain import get_client, run_turn
from personas import DEFAULT, PERSONAS
from voice import Voice, engine_name
from voice_state import STATE, emotion_register, load_persisted

tools.load_all()   # every capability registers here — identical set everywhere
from tools import system_admin  # noqa: E402 — for mid-flight aborts

EXIT_WORDS = {"quit", "exit", "goodbye", "good bye", "bye"}


def _is_noise(text: str) -> bool:
    """Non-speech: empty, whisper's [BLANK_AUDIO], or sound annotations like
    '(wind blowing)' / '[music]' — never send these to the brain as user words."""
    t = text.strip().lower()
    if t in {"", "[blank_audio]", "[ blank_audio ]"}:
        return True
    return bool(re.fullmatch(r"[\(\[\*][^)\]]*[\)\]\*]?[.!?]*", t))


def _is_echo(text: str, last_reply: str) -> bool:
    """Guard against hearing Jarvis's own trailing speech/room echo (or whisper
    hallucinating reply-like text from noise): too similar to what he just said."""
    import difflib
    if not last_reply:
        return False
    return difflib.SequenceMatcher(
        None, text.lower().strip(), last_reply.lower().strip()).ratio() > 0.7
SLEEP_WORDS = {"sleep", "go to sleep", "go back to sleep", "that's all", "that is all",
               "thats all", "never mind", "nevermind", "that's it", "dismiss", "stand down"}
AFFIRM = {"yes", "yeah", "yep", "yup", "sure", "confirm", "confirmed", "proceed",
          "affirmative", "approved", "go"}
NEGATE = {"no", "nope", "don't", "dont", "not", "cancel", "stop", "wait", "never",
          "negative", "abort"}
ABORT_WORDS = {"stop", "abort", "cancel", "stop it", "abort it", "cancel it",
               "kill it", "stop that", "abort that"}

# Persona-flavoured lines — Jarvis and Friday should never sound generic.
LINE = {
    "Jarvis": {"empty": "Done, sir.", "error": "My apologies, sir — I hit a snag with that.",
               "cancel": "Very well, sir — cancelled.",
               "sleep": "Going quiet, sir. Say Hey Jarvis when you need me.",
               "here": "Jarvis here, sir.",
               "confirm": "To confirm, sir: I will {d}. Shall I proceed?",
               "working": "On it, sir — {d}. Say stop if you change your mind.",
               "aborted": "Stopped, sir.", "still": "Still working on it, sir."},
    "Friday": {"empty": "Done, boss.", "error": "Hmm, that one broke on me, boss.",
               "cancel": "Okay boss, cancelled.",
               "sleep": "Going quiet, boss. Call me when you need me.",
               "here": "Friday here, boss.",
               "confirm": "Just checking, boss: I'll {d}. Good to go?",
               "working": "On it, boss — {d}. Say stop if you change your mind.",
               "aborted": "Stopped it, boss.", "still": "Still on it, boss."},
}


def _line(persona, key, **kw) -> str:
    return LINE.get(persona.name, LINE["Jarvis"])[key].format(**kw)


def _affirmative(text: str) -> bool:
    """Strict yes/no for GATED actions. Negations win over anything else, so
    'please don't' / 'don't do it' can never fire the action (safety)."""
    words = set(re.sub(r"[^\w\s']", " ", text.lower()).split())
    if words & NEGATE:
        return False
    if any(p in text.lower() for p in ("go ahead", "do it", "please do", "go for it")):
        return True
    return bool(words & AFFIRM)


def _persona_from(text: str, active):
    """If the user addresses a persona, return (that persona, remaining text).
    Always strips the name — even for the active persona."""
    low = text.strip().lower()
    for key, p in PERSONAS.items():
        if (low == key or low.startswith((key + " ", key + ",")) or
                f"switch to {key}" in low or low.startswith(f"hey {key}")):
            stripped = re.sub(r"^\s*(hey\s+|switch to\s+)?" + key + r"[\s,:.!?]*", "",
                              text.strip(), flags=re.I)
            return p, stripped.strip()
    return active, text


def _summarize(persona, res) -> str:
    """Turn a finished gated-action result into a short spoken line."""
    if not isinstance(res, dict):
        return _line(persona, "empty")
    if res.get("error"):
        return f"That failed: {str(res['error'])[:120]}"
    r = res.get("result", res)
    if isinstance(r, dict):
        if r.get("stderr", "").strip():
            return f"Finished, but with an error: {r['stderr'].strip()[:150]}"
        if "stdout" in r:
            out = r["stdout"].strip()
            return f"Done. Output: {out[:200]}" if out else "Done, no output."
        if r.get("installed"):
            return f"Installed {r['installed']}."
        if r.get("ok") is False:
            return f"That install didn't work: {str(r.get('output', ''))[:150]}"
    return _line(persona, "empty")


def build_system(persona) -> str:
    system = persona.system_prompt
    if emotion_register(STATE.emotion):
        system += " " + emotion_register(STATE.emotion)
    if memory.build_context():
        system += "\n\n" + memory.build_context()
    return system


def _end_session(history: list) -> None:
    """Summarize the finished conversation into long-term memory (so the NEXT
    session knows what you talked about). Online: the brain writes 2 lines.
    Offline: store a cheap truncation instead of loading the 7B just for this."""
    if not history:
        return
    try:
        if brain.use_groq():
            convo = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in history[-10:])
            s = brain.ask("Summarize this conversation in at most 2 short sentences, "
                          "third person, keep concrete facts:\n" + convo)
        else:
            s = " / ".join(m["content"][:80] for m in history[-2:])
        memory.save_session_summary(s)
    except Exception:
        pass
    history.clear()


def main() -> None:
    args = sys.argv[1:]
    persona = PERSONAS[args[0].lower()] if args and args[0].lower() in PERSONAS else DEFAULT
    STATE.name, STATE.voice_ref, STATE.rate = persona.name, persona.voice, persona.speed
    load_persisted()

    _, model, label = get_client()
    print(f"[{STATE.name} · engine={engine_name()} · brain={label}:{model}]")
    # Warm the voice FIRST and in the background — it's the slowest load, so it
    # needs every second of head start it can get (see the 30s-hang postmortem).
    voice = Voice()
    warmer: threading.Thread | None = threading.Thread(target=voice.warmup, daemon=True)
    warmer.start()
    print("Loading wake word + VAD… (voice warming in background)")
    wake_thr = float(os.getenv("JARVIS_WAKE_THRESHOLD", "0.5"))
    listener = ears.Ears(wakeword="hey_jarvis", wake_threshold=wake_thr)

    barge_mode = os.getenv("JARVIS_BARGE_IN", "off").lower()
    followup = os.getenv("JARVIS_FOLLOWUP", "1") != "0"
    # How long he keeps listening for a follow-up before the conversation ends.
    followup_window = float(os.getenv("JARVIS_FOLLOWUP_WINDOW", "120"))
    sleep_after = float(os.getenv("JARVIS_SLEEP_AFTER", "300"))
    CUE = {"Jarvis": "Sir?", "Friday": "Boss?"}

    listener.start()
    print('Ready. Say "Hey Jarvis" to wake me — then just keep talking. '
          f'[barge-in: {barge_mode}]  (Ctrl-C to stop)')

    skip_wake = False
    models_warm = True
    history: list[dict] = []            # this session's exchanges
    last_reply = ""                     # for the self-echo guard

    def _on_term(*_):
        # launchd/kill: persist the conversation summary before dying.
        _end_session(history)
        listener.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _on_term)
    action: dict | None = None          # a confirmed gated action running in background
    last_active = time.time()

    try:
        while True:
            if not skip_wake:
                if not listener.poll_wake(15):
                    if sleep_after > 0 and models_warm and \
                            time.time() - last_active > sleep_after:
                        _end_session(history)
                        voice.unload(); models_warm = False
                        print("💤 deep sleep — voice model released to free RAM")
                    continue
                if not models_warm:
                    warmer = threading.Thread(target=voice.warmup, daemon=True)
                    warmer.start()
                    models_warm = True
                print("… listening", flush=True)
                # Two-stage listen: if you spoke in one breath ("Hey Jarvis what
                # time is it") we catch it immediately; if you said just "Hey
                # Jarvis" and paused, he ACKNOWLEDGES out loud ("Sir?") so you
                # know he's live without watching a terminal.
                audio = listener.capture(skip_wake=True, start_timeout_sec=1.4)
                if audio.size == 0 and not (warmer is not None and warmer.is_alive()):
                    listener.pause()
                    voice.say(CUE.get(persona.name, "Yes?")); voice.wait()
                    listener.resume()
                    print(f"   ({CUE.get(persona.name)})", flush=True)
                    audio = listener.capture(skip_wake=True, start_timeout_sec=10)
            else:
                print("… (go on)", flush=True)
                audio = listener.capture(skip_wake=True,
                                         start_timeout_sec=followup_window)
            # Bias STT with the USER's recent words + known place names. Never the
            # assistant's own replies — with background noise, whisper hallucinates
            # text resembling its hint (the "clarify, sir" loop).
            hint = " ".join(m["content"] for m in history[-4:] if m["role"] == "user")
            hint = (memory.recall("known_places") or "") + ". " + hint
            text = ears.transcribe(audio, hint=hint)
            if _is_noise(text):
                if skip_wake:
                    skip_wake = False
                    print('   (conversation over — say "Hey Jarvis" to wake me)')
                else:
                    print("   (didn't catch that)")
                continue
            if _is_echo(text, last_reply):
                print(f"   (ignored own echo: {text[:50]!r})")
                continue
            print(f"you   : {text}")

            new_p, text = _persona_from(text, persona)
            if new_p is not persona:
                persona = new_p
                STATE.name, STATE.voice_ref, STATE.rate = \
                    persona.name, persona.voice, persona.speed

            bare = text.strip().lower().rstrip(".!?")

            # A background action (install/command) may have finished — report it.
            preface = ""
            if action is not None and not action["thread"].is_alive():
                preface = _summarize(persona, action["result"].get("value"))
                action = None

            if bare in EXIT_WORDS:
                brain.cancel_pending()
                if action is not None:
                    system_admin.abort_current()
                _end_session(history)
                voice.say("Goodbye."); voice.wait()
                break

            going_to_sleep = bare in SLEEP_WORDS
            t0 = time.time()
            try:
                if action is not None and bare in ABORT_WORDS:
                    # Mid-flight abort of the running install/command.
                    system_admin.abort_current()
                    action["thread"].join(timeout=5)
                    action = None
                    reply = _line(persona, "aborted")
                elif not bare:
                    reply = _line(persona, "here")
                elif going_to_sleep:
                    brain.cancel_pending()
                    _end_session(history)
                    reply = _line(persona, "sleep")
                elif brain.PENDING is not None:
                    if _affirmative(text):
                        # Run the confirmed action in the BACKGROUND so Jarvis keeps
                        # listening — and "stop"/"abort" can kill it mid-flight.
                        desc = brain.describe_pending()
                        holder = {"value": None}

                        def _runner(h=holder):
                            h["value"] = brain.confirm_pending()

                        th = threading.Thread(target=_runner, daemon=True)
                        th.start()
                        action = {"thread": th, "result": holder, "desc": desc}
                        reply = _line(persona, "working", d=desc)
                    else:
                        brain.cancel_pending()
                        if len(bare.split()) > 2:
                            reply = run_turn(text, build_system(persona), history)
                        else:
                            reply = _line(persona, "cancel")
                else:
                    last_active = time.time()
                    reply = run_turn(text, build_system(persona), history)

                if brain.PENDING is not None:
                    # A gated call was requested THIS turn → the SYSTEM states the
                    # exact action (never the model's paraphrase).
                    reply = _line(persona, "confirm", d=brain.describe_pending())
            except Exception as e:
                print(f"[turn error] {type(e).__name__}: {e}", flush=True)
                reply = _line(persona, "error")

            if not reply or not reply.strip():
                reply = _line(persona, "empty")
            last_reply = reply
            if preface:
                reply = f"{preface} {reply}" if reply != _line(persona, "empty") else preface
            print(f"{persona.name.lower()} ({time.time()-t0:.1f}s): {reply}")

            # Session + long-term memory of the conversation itself.
            if text.strip() and not going_to_sleep and brain.PENDING is None:
                history.append({"role": "user", "content": text})
                history.append({"role": "assistant", "content": reply})
                del history[:-12]
                memory.log_exchange(text, reply)

            if warmer is not None and warmer.is_alive():
                print("   (voice model still warming — one moment…)", flush=True)
                warmer.join()          # voice must be loaded before speaking
            warmer = None

            interrupted = False
            try:
                if barge_mode == "off":
                    # Step tracing: any stage >2s prints itself, so a stall is
                    # never anonymous again.
                    ts = time.time()
                    listener.pause()           # release mic → full speaker quality
                    if time.time() - ts > 2:
                        print(f"   [trace] mic pause: {time.time()-ts:.1f}s", flush=True)
                    ts = time.time()
                    voice.say(reply); voice.wait()
                    if time.time() - ts > 2:
                        print(f"   [trace] speak: {time.time()-ts:.1f}s", flush=True)
                    ts = time.time()
                    listener.resume()
                    if time.time() - ts > 2:
                        print(f"   [trace] mic resume: {time.time()-ts:.1f}s", flush=True)
                else:
                    voice.say(reply)
                    interrupted = listener.monitor_while_speaking(voice, mode=barge_mode)
                    if interrupted:
                        print("   (you cut in — go ahead)")
            except Exception as e:
                # Audio path hiccup must never kill the daemon or leave it deaf.
                print(f"[audio error] {type(e).__name__}: {e} — recovering…", flush=True)
                try:
                    listener.resume()
                except Exception:
                    pass
            last_active = time.time()
            skip_wake = False if going_to_sleep else (interrupted or followup)
    except KeyboardInterrupt:
        print("\n[stopped]")
        _end_session(history)
    finally:
        listener.close()


if __name__ == "__main__":
    main()
