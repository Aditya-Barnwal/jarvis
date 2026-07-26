"""Phase 1/2 driver — voice engine + live control + persistent memory.

Seeds the live voice STATE from the chosen persona, restores anything you set in
a past session (name, voice), injects known facts, runs a tool-enabled brain turn
(so "be angry", "call yourself Vega", "go deeper", "slow down" actually take
effect), and speaks the reply in the current voice state.

Run:
    source .venv/bin/activate
    python src/hello_jarvis.py                          # Jarvis
    python src/hello_jarvis.py friday "brief me"         # Friday persona
    python src/hello_jarvis.py "call yourself Vega and say hi"
    python src/hello_jarvis.py "be angry and tell me time's up"
"""
import sys

import memory
import tools
tools.load_all()   # identical tool set across all entry points
from brain import get_client, run_turn
from personas import DEFAULT, PERSONAS
from voice import Voice, engine_name
from voice_state import STATE, emotion_register, load_persisted


def main() -> None:
    args = sys.argv[1:]
    persona = DEFAULT
    if args and args[0].lower() in PERSONAS:
        persona = PERSONAS[args.pop(0).lower()]
    prompt = " ".join(args) or "Introduce yourself in one short sentence."

    # Seed live state from the persona, then let persisted settings win.
    STATE.name = persona.name
    STATE.voice_ref = persona.voice
    STATE.rate = persona.speed
    load_persisted()

    system = persona.system_prompt
    if emotion_register(STATE.emotion):
        system += " " + emotion_register(STATE.emotion)
    if memory.build_context():
        system += "\n\n" + memory.build_context()

    _, model, label = get_client()
    print(f"[{STATE.name} · voice={STATE.voice_ref} · engine={engine_name()} · "
          f"brain={label}:{model}]")
    print(f"you   : {prompt}")

    reply = run_turn(prompt, system)
    print(f"{STATE.name.lower()}: {reply}")
    print(f"[state: emotion={STATE.emotion} pitch={STATE.pitch_semitones} "
          f"rate={STATE.rate} voice={STATE.voice_ref} name={STATE.name}]")

    voice = Voice()
    voice.say(reply)
    voice.wait()


if __name__ == "__main__":
    main()
