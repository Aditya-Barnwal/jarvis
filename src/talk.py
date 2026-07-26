"""Phase 1 · Milestone 2 — press-to-talk voice assistant.

Full loop: mic → whisper.cpp (STT) → brain (Groq/Ollama, tool-enabled) →
Kokoro voice, in the active persona with live voice controls and memory.

Run:
    source .venv/bin/activate
    python src/talk.py                # Jarvis
    python src/talk.py friday         # Friday persona
Say "quit" / "exit" (or Ctrl-C) to stop.
"""
import sys

import ears
import memory
import tools
tools.load_all()   # identical tool set across all entry points
from brain import get_client, run_turn
from personas import DEFAULT, PERSONAS
from voice import Voice, engine_name
from voice_state import STATE, emotion_register, load_persisted

EXIT_WORDS = {"quit", "exit", "stop", "goodbye", "good bye", "bye"}


def build_system(persona) -> str:
    system = persona.system_prompt
    if emotion_register(STATE.emotion):
        system += " " + emotion_register(STATE.emotion)
    if memory.build_context():
        system += "\n\n" + memory.build_context()
    return system


def main() -> None:
    args = sys.argv[1:]
    persona = PERSONAS[args[0].lower()] if args and args[0].lower() in PERSONAS else DEFAULT

    STATE.name, STATE.voice_ref, STATE.rate = persona.name, persona.voice, persona.speed
    load_persisted()

    _, model, label = get_client()
    print(f"[{STATE.name} · engine={engine_name()} · brain={label}:{model}] "
          f"— press-to-talk. Say 'quit' to exit.")

    voice = Voice()
    try:
        while True:
            audio = ears.record_until_enter()
            text = ears.transcribe(audio)
            if not text:
                print("   (didn't catch that)")
                continue
            print(f"you   : {text}")
            if text.strip().lower().rstrip(".!?") in EXIT_WORDS:
                voice.say("Goodbye."); voice.wait()
                break
            reply = run_turn(text, build_system(persona))
            print(f"{STATE.name.lower()}: {reply}")
            voice.say(reply)
            voice.wait()
    except (KeyboardInterrupt, EOFError):
        print("\n[stopped]")


if __name__ == "__main__":
    main()
