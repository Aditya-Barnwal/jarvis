# Voices & personas — Jarvis (male) + Friday (female)

Two assistants, two voices, one system: **Jarvis** (refined British male) and **Friday** (sophisticated British female). This doc gives you the full audition set, my picks, the dual-persona wiring, and — most importantly — how to make them **natural and low-latency**, not the choppy Mac voice.

Hand this straight to your CLI/VS Code agent as the spec for the voice layer. Everything here is local, offline-capable, and free (Kokoro, Apache-2.0).

---

## The lag problem — read this first

If it sounds slow or robotic like the Mac voice, it's almost never Kokoro itself. Kokoro runs **faster than real-time on an M1** (it hit #1 on the TTS Arena; most people can't tell it from ElevenLabs on clean text). Three things cause the bad experience, all fixable:

1. **Cold model every turn** → load Kokoro **once** and keep it warm in the daemon. Reloading per reply is the #1 cause of "lag."
2. **Synthesizing the whole reply before playing** → **stream sentence-by-sentence.** Start speaking sentence one while sentence two is still being made. Time-to-first-audio drops to ~0.3s.
3. **Accidentally falling back to macOS `say`** → that's the robotic voice. Check for and remove any `say` fallback (see bottom).

Do these three and it feels like talking to a real assistant, not a screen reader. Code for all three is in the "Natural, low-latency playback" section below.

---

## Full audition set

Kokoro's British voices, with character and quality grade (A–F, higher = better training data). Grade is quality, not fit — pick by *sound*, not grade alone.

### British male — Jarvis candidates

| Voice ID | Character | Pitch | Grade | Jarvis fit |
|---|---|---|---|---|
| `bm_george` | Classic British, authoritative, commanding | 138 Hz | C | ★ **top pick** — the definitive butler-AI tone |
| `bm_lewis` | Modern British, reliable, articulate | 102 Hz (deeper) | D+ | great for a **deeper** Jarvis; blend with george |
| `bm_daniel` | Polished, modern, professional, versatile | — | D | clean, slightly younger |
| `bm_fable` | Narrative, expressive, storytelling | — | C | warmer, more theatrical |

### British female — Friday candidates

| Voice ID | Character | Grade | Friday fit |
|---|---|---|---|
| `bf_emma` | Warm, refined, elegant, sophisticated | **B-** (best female) | ★ **top pick** — polished female AI |
| `bf_isabella` | Professional, articulate, sophisticated, clear | C | crisp, corporate Friday |
| `bf_alice` | Refined, elegant, clear, engaging | D | softer, storytelling feel |
| `bf_lily` | Sweet, gentle, pleasant, approachable | D | friendliest, least "AI" |

(If you ever want non-British options, American voices exist too — males `am_onyx`/`am_michael`/`am_adam`, females `af_heart`/`af_nicole`/`af_bella` — but British sells the Jarvis/Friday vibe.)

### One-command audition (hear them all saying the same line)

Install a Kokoro CLI, then run each. Use British English (`en-gb`) and a measured speed:

```bash
uv tool install git+https://github.com/nazdridoy/kokoro-tts   # one-time

# JARVIS candidates
for v in bm_george bm_lewis bm_daniel bm_fable; do
  echo ">>> $v"
  echo "Good evening, sir. All systems are online and operating within normal parameters." \
    | kokoro-tts - --stream --voice $v --lang en-gb --speed 0.95
done

# FRIDAY candidates
for v in bf_emma bf_isabella bf_alice bf_lily; do
  echo ">>> $v"
  echo "Boss, the markets just closed. Shall I run through your day?" \
    | kokoro-tts - --stream --voice $v --lang en-gb --speed 0.98
done
```

### Or audition from Python (also tries blends)

```python
# audition.py — plays every candidate, plus a couple of blends
from kokoro import KPipeline
import sounddevice as sd, numpy as np

pipe = KPipeline(lang_code="b")   # 'b' = British — important!

JARVIS_LINE = "Good evening, sir. All systems are online and operating within normal parameters."
FRIDAY_LINE = "Boss, the markets just closed. Shall I run through your day?"

def play(text, voice, speed=0.95):
    print(f">>> {voice}")
    audio = np.concatenate([a for _, _, a in pipe(text, voice=voice, speed=speed)])
    sd.play(audio, 24000); sd.wait()

for v in ["bm_george", "bm_lewis", "bm_daniel", "bm_fable"]:
    play(JARVIS_LINE, v)
for v in ["bf_emma", "bf_isabella", "bf_alice", "bf_lily"]:
    play(FRIDAY_LINE, v, speed=0.98)
```

---

## My picks (and blends)

- **Jarvis → `bm_george`.** The classic authoritative British AI. For a deeper, more commanding tone, blend in `bm_lewis`: `bm_george:0.7, bm_lewis:0.3`.
- **Friday → `bf_emma`.** Highest-quality female voice, warm and refined. For a crisper, more clinical Friday, blend toward isabella: `bf_emma:0.6, bf_isabella:0.4`.

Blending from the CLI:

```bash
echo "Certainly, sir." | kokoro-tts - --stream --voice "bm_george:0.7,bm_lewis:0.3" --lang en-gb --speed 0.95
```

Blends in the `kokoro` Python package are done by averaging the two voice embedding tensors; the CLI above is the easy path for auditioning ratios before you commit one.

---

## Natural, low-latency playback (the important engineering)

This is what kills the lag. Two techniques: **warm model** + **sentence streaming**.

```python
# src/voice.py
import re, queue, threading
import sounddevice as sd, numpy as np
from kokoro import KPipeline

SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')

class Voice:
    """Warm, streaming TTS. Load once; speaks sentence-by-sentence for ~0.3s
    time-to-first-audio instead of waiting for the whole reply."""
    def __init__(self, voice="bm_george", speed=0.95, lang="b"):
        self.pipe = KPipeline(lang_code=lang)   # loaded ONCE, stays warm
        self.voice, self.speed = voice, speed
        self._q = queue.Queue()
        threading.Thread(target=self._player, daemon=True).start()

    def _player(self):
        # dedicated thread: plays audio chunks as they arrive, gaplessly
        while True:
            audio = self._q.get()
            sd.play(audio, 24000); sd.wait()

    def say(self, text: str):
        # split into sentences; synthesize + enqueue each as it's ready
        for sentence in SENT_SPLIT.split(text.strip()):
            if not sentence:
                continue
            audio = np.concatenate(
                [a for _, _, a in self.pipe(sentence, voice=self.voice, speed=self.speed)]
            )
            self._q.put(audio)   # playback thread starts speaking sentence 1
                                 # while we synthesize sentence 2

    def set_voice(self, voice, speed=None):
        self.voice = voice
        if speed: self.speed = speed
```

### Even lower latency: stream from the brain too

The real magic is not waiting for the full LLM reply. Groq streams tokens; accumulate until you hit a sentence boundary, then fire that sentence at `Voice.say()` immediately:

```python
# in the daemon turn handler
buf = ""
for token in stream_brain_reply(user_text):      # Groq streaming
    buf += token
    if re.search(r'[.!?]\s', buf):               # sentence complete
        sentence, buf = split_first_sentence(buf)
        voice.say(sentence)                       # speak it NOW
if buf.strip():
    voice.say(buf)
```

Now Jarvis starts talking a fraction of a second after the brain begins responding — the whole turn *feels* instant even for a long answer. On an M1, Kokoro synthesizes faster than it plays, so it never becomes the bottleneck.

### Optional "in-the-room AI" sheen

Subtle only — overdone effects sound cheap, not Jarvis:

```python
from pedalboard import Pedalboard, Reverb, HighpassFilter, Compressor
FX = Pedalboard([HighpassFilter(90), Compressor(threshold_db=-18, ratio=2.5),
                 Reverb(room_size=0.12, wet_level=0.06)])
# run each chunk through FX(audio, 24000) before enqueueing
```

---

## Running both: the persona system

Jarvis and Friday are two **personas** — each is a voice + a system prompt. You switch by voice command ("Friday, take over" / "Jarvis"), and the daemon swaps both the voice and the brain's persona prompt.

```python
# src/personas.py
from dataclasses import dataclass

@dataclass
class Persona:
    name: str
    voice: str
    speed: float
    system_prompt: str

JARVIS = Persona(
    name="Jarvis", voice="bm_george", speed=0.95,
    system_prompt=(
        "You are Jarvis, a calm, refined British butler-engineer AI. Speak concisely "
        "and precisely, with dry understatement. Address the user as 'sir' occasionally. "
        "One well-chosen sentence beats three. No emoji, no exclamation marks."
    ),
)

FRIDAY = Persona(
    name="Friday", voice="bf_emma", speed=0.98,
    system_prompt=(
        "You are Friday, a sharp, warm, efficient female AI assistant. Speak naturally "
        "and briskly, friendly but economical. Address the user as 'boss' occasionally. "
        "Get to the point. No emoji, no exclamation marks."
    ),
)

PERSONAS = {"jarvis": JARVIS, "friday": FRIDAY}
```

```python
# src/tools/persona_switch.py
from brain import tool
from personas import PERSONAS

@tool({"name": "switch_persona",
       "description": "Switch the active assistant persona/voice.",
       "parameters": {"type": "object",
           "properties": {"name": {"type": "string", "enum": ["jarvis", "friday"]}},
           "required": ["name"]}})
def switch_persona(name: str):
    p = PERSONAS[name.lower()]
    daemon.set_persona(p)          # updates voice.set_voice(p.voice, p.speed) + system prompt
    return {"active": p.name}
```

The daemon holds `active_persona`; every brain call uses its `system_prompt`, and `Voice` uses its `voice`+`speed`. Saying "Friday" mid-conversation flips both. You can even give each its own wake word later (openWakeWord can run "hey jarvis" and "hey friday" models simultaneously — it handles many at once), so "Hey Friday…" wakes her directly.

---

## Honest limits

- **No Irish accent / no cloning in Kokoro.** Friday is Irish in the films; Kokoro is English (US/British) only and can't clone voices (its training set is too small). British female (`bf_emma`) is the clean local stand-in. If an Irish Friday really matters, that's a cloning-model job — see below.
- **Even, neutral tone.** Kokoro nails calm, composed delivery (perfect for Jarvis/Friday) but doesn't do big emotional swings. For a composed AI assistant that's a feature, not a flaw.
- **Occasional trip-ups** on odd names/abbreviations — spell tricky ones phonetically in text if needed.

### If you later want a truly custom/Irish voice (the legit cloning route)

Cloning tools clone from a short reference clip: **Chatterbox**, **F5-TTS**, **XTTS v2**. The clean way to use them: record **your own** voice, or use a voice actor / dataset you've **licensed** (including an Irish VA for Friday). Point the tool at a voice you have the right to use, wrap it behind the same `Voice.say()` interface, and nothing else in Jarvis changes. (Same reasoning as before — I'd keep it to voices you own or have licensed, not a clone of a specific film performance.)

---

## "Am I on the Mac voice?" check

```bash
grep -rn "say" src/       # any subprocess.run(["say", ...]) is the robotic Mac fallback — remove it
```

If a `say` fallback is catching a Kokoro error, you'll hear the Mac voice and think Kokoro failed. Fix the underlying Kokoro call instead of falling back.

---

## Agent checklist

- [ ] Confirm TTS is Kokoro, not `say` (remove any `say` fallback).
- [ ] `lang_code="b"` (British) — not `a`.
- [ ] Jarvis = `bm_george` @ 0.95; Friday = `bf_emma` @ 0.98. Audition blends if you want.
- [ ] Load Kokoro **once** in the daemon (warm model).
- [ ] **Stream sentence-by-sentence** via the `Voice` queue (kills the lag).
- [ ] Stream brain tokens → speak on sentence boundaries (feels instant).
- [ ] Add the `Persona` system + `switch_persona` tool for Jarvis/Friday.
- [ ] (Optional) subtle `pedalboard` FX; (optional) separate "hey friday" wake word.
