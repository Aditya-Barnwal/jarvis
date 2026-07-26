# Deep analysis — findings, loopholes & the plan for a "perfect Jarvis on 8 GB"

Full project review (code + docs), 2026-07-18. Every fix below is **free** (code-only).

> ✅ **STATUS UPDATE (same day): ALL items below are IMPLEMENTED and test-verified** except
> F11 (watch-along video), F12 (speaker verification), and the weekly memory-consolidation
> cron — those three remain future work. Verified in the polish pass: negation-safe gate
> ("please don't" can no longer fire an action), crash-proof voice/STT/turn/mic paths,
> system-stated exact confirmations, session history ("and tomorrow?" works), first-sentence
> fast speech, lean prompt, free 120B escalation, real-Chrome Gmail, `search_nearby` on GPS
> coords, vision model evicted after use, memory dedupe, log truncation, doc banners.

---

## A. Critical bugs (verified by testing, fix first)

### A1. 🔴 The confirmation gate says YES to "please don't" — SAFETY BUG
`_affirmative()` in `listen.py` checks if any affirmative *word/phrase appears anywhere*:
- `_affirmative("please don't")` → **True** ("please" is in AFFIRM)
- `_affirmative("don't do it")` → **True** ("do it" matches as a substring)

So refusing a pending **install/shell command** with natural phrasing can **execute it**.
**Fix (free):** check negations FIRST — if the text contains "don't", "do not", "no", "cancel",
"stop", "wait" → treat as NO regardless of other words. Only then look for affirmatives.
A stricter option: require an explicit "yes"/"confirm" for gated actions, full stop.

### A2. 🔴 One error in the voice pipeline = permanently mute
`voice.py` workers (`_synth_worker`, `_play_worker`) use `try/finally` with **no `except`** —
any exception (a Kokoro hiccup, an audio-device change) propagates and **kills the thread**.
The daemon keeps running but never speaks again, silently.
**Fix:** wrap loop bodies in `except Exception: log + continue`. Two lines.

### A3. 🔴 Any brain/network error crashes the whole daemon
`listen.py` calls `run_turn(...)` with **no try/except**. A Groq timeout, a rate-limit 429, or
a dropped connection kills the process mid-conversation. (launchd restarts it, but that's a
full cold reload — models re-warm, session lost.)
**Fix:** `try/except` around the turn → speak "Sorry, I hit an error" + continue the loop.

### A4. 🔴 Whisper failure crashes the loop
`ears.transcribe()` uses `subprocess.run(..., check=True)` — if whisper-cli fails once (bad
audio, OOM under pressure), the exception propagates → daemon dies.
**Fix:** drop `check=True`, return `""` on failure (the loop already handles empty text).

### A5. 🟠 Mic device loss (Bluetooth disconnect) = crash
`poll_wake`/`capture` read the stream with no error handling. If BT earphones disconnect
mid-session (extremely realistic), PortAudio raises → daemon dies.
**Fix:** catch stream errors → close + reopen the default input device → continue.

---

## B. Security & safety loopholes

### B1. 🔴 Prompt injection via web content → deceptive confirmation
`read_page`/`web_search` feed raw page text to the model. A malicious page could instruct it to
call `run_command` with something nasty, and the *model* is what phrases the confirmation —
it could paraphrase deceptively ("I'll just tidy some files — confirm?").
**Fix (free, important):** `listen.py` must speak the **exact pending command itself** from
`brain.PENDING` ("The command is: curl … | sh — yes or no?") instead of trusting the model's
phrasing. The data is already in `PENDING`; never let the model summarize its own gated action.

### B2. 🟠 The `run_command` "sandbox" is cosmetic
`cwd=data/workspace` but `shell=True` allows `cd /`, absolute paths, `rm -rf ~`, pipes to sh.
The gate is the real protection (plus B1's fix). **Optional hardening:** block obviously
destructive patterns (`rm -rf /`, `sudo`, `> /dev/`, `curl|sh`) before even gating; run with a
restricted PATH; cap output size. Don't pretend it's a jail — say it in the confirm.

### B3. 🟠 Two gated calls in one turn overwrite each other
`brain.PENDING` is a single slot — if the model requests two gated actions in one turn, only
the last survives; the user may confirm something different from what was described.
**Fix:** make PENDING a list, confirm them one at a time (or reject multi-gated turns).

### B4. 🟡 Browser profile holds your Gmail session in plaintext-ish form
`data/browser/` (Playwright persistent profile) stores logged-in cookies on disk. Fine for a
personal machine, but it's in the project folder — ensure `data/` stays git-ignored (it is)
and note it in privacy docs. Consider `chmod 700 data/browser`.

### B5. 🟡 Groq key hygiene
The key was pasted in chat once — rotate it at console.groq.com/keys when convenient.

---

## C. UX gaps (what makes it feel less like Jarvis)

### C1. 🔴 No conversation memory *within a session*
Every `run_turn` is stateless — only long-term facts are injected. Ask "what's the weather?"
then "and tomorrow?" → the brain has **no idea** what "and tomorrow" refers to. This is the
single biggest "it doesn't feel smart" gap, and the fix is cheap:
**Fix:** keep a rolling history (last ~6–8 exchanges) in `listen.py`, pass as prior messages
to `run_turn`, reset on sleep. Costs a few hundred tokens; Groq handles it fine.

### C2. 🟠 Saying anything-but-yes to a pending action *discards your words*
If a gated action is pending and you say "actually, what's the time?", the loop cancels the
action and replies "Alright, I won't." — your actual question is thrown away.
**Fix:** cancel, then feed the same text through `run_turn` as a normal turn.

### C3. 🟠 Empty replies = silent Jarvis
Models occasionally return "" (seen with weak models / after tool loops). The loop prints and
"speaks" nothing — feels broken. **Fix:** fallback line ("Done." / "Sorry, say that again?").

### C4. 🟠 Waking from deep sleep loses your first words
After idle-unload, wake → `voice.warmup()` blocks ~3.5s **before** capture starts — if you
kept talking, that speech is gone. **Fix:** capture first, warm up in a background thread
while recording/thinking (the voice isn't needed until reply time).

### C5. 🟡 Reply latency could feel 2× snappier
`stream_reply()` exists in brain.py but is **unused** — the loop waits for the full LLM reply,
then synthesizes the whole thing, then speaks. **Fix:** stream tokens → speak the first
sentence while the rest generates (the machinery is already written; wire it for non-tool
replies). Also: `get_client()` re-runs a socket check every call — cache `is_online()` for
~30s to shave latency.

### C6. 🟡 Entry points diverge
`talk.py` and `hello_jarvis.py` import only 2 tool modules vs `listen.py`'s 10 — same phrase
gives different behavior across entry points. **Fix:** one `tools/__init__.load_all()` used
everywhere.

### C7. 🟡 "Jarvis, …" while Jarvis is active isn't stripped
`_persona_from` only strips the name on a *switch*, so "Jarvis, open Safari" (already Jarvis)
sends the literal "Jarvis, open Safari" to the brain. Harmless, but strip it always.

---

## D. Performance & the 8 GB RAM master plan 😅

The guiding rule: **at most ONE big model resident at a time, and prefer zero.**

| Component | RAM | Strategy |
|---|---|---|
| Brain (online) | **0** | Groq — keep as primary. Free, fast. |
| Brain (offline) | ~5 GB | qwen2.5:7b loads only when offline. Accept slower offline. |
| Kokoro TTS | ~1 GB | Warm while active; idle-unload after `JARVIS_SLEEP_AFTER` (done). |
| Whisper small.en | ~0.5 GB | Loads per-utterance via whisper-cli; fine. |
| Vision qwen2.5vl:3b | ~3 GB | **The problem child** — see D1. |
| openWakeWord + VAD | tiny | Always on; that's the Siri-style idle state. |

### D1. 🟠 Vision model stays resident after use (Ollama default keep-alive ≈ 5 min)
After `see_screen`, 3 GB sits in RAM for minutes; if anything else loads meanwhile → swap/heat.
**Fix (free, one line):** send `keep_alive: 0` with the vision request (Ollama unloads the
model immediately after answering). First call stays slow (~2–3 min load on 8 GB — that's
physics), but it never *lingers*. Alternative trade: `moondream` (1.7 GB, faster load, weaker
text-reading) — flip via `JARVIS_VISION_MODEL`. Optional cloud path: Gemini's free tier does
vision well at 0 local RAM, but the screenshot leaves the machine — privacy trade the user
must explicitly opt into. Local stays the default.

### D2. 🟠 Token bloat: 31 schemas + a giant capabilities paragraph EVERY turn
The nudge in `run_turn` duplicates what the schemas already say, and grows with every tool.
Cost: slower turns, and free-tier rate limits get closer with heavy use.
**Fix:** cut the nudge to 2 sentences (behavioral rules only — "prefer tools; app-first-then-
website; never claim gated actions are done") and let the schemas carry the details. Trim the
fattest tool descriptions. ~40% prompt reduction, free speed.

### D3. 🟡 Memory grows unbounded and is dumped wholesale into every prompt
`remember_fact` never dedupes ("meeting at 4" ×5), and `build_context` injects the last 50
facts every turn, forever. Over months this bloats prompts and confuses the brain.
**Fix:** dedupe on insert (exact/near match), and add a weekly "consolidate" pass where the
brain rewrites the fact list into a clean short set (LEARNING.md already envisions this).

### D4. 🟡 Daemon logs grow forever
`logs/daemon.out.log` has no rotation. **Fix:** `newsyslog` entry or truncate-at-startup.

### D5. Idea: two-tier Groq brain
`gpt-oss-20b` for everything (fast) + auto-escalate to `gpt-oss-120b` (also free on Groq) when
the request looks hard (long reasoning, code review, teaching). One `if` on prompt length/verb.
Free capability boost, zero RAM.

---

## E. Documentation drift (blueprint vs reality)

The root planning docs now contradict the built system — confusing for any new model/CLI:

| Doc | Says | Reality |
|---|---|---|
| ARCHITECTURE.md, DECISIONS.md, SETUP.md, OFFLINE.md, phase docs | online brain = `llama-3.3-70b-versatile` | `openai/gpt-oss-20b` (70b was flaky at tools) |
| SETUP.md | TTS = `kokoro-mlx`, whisper `base.en` | `kokoro` pip pkg; `small.en` preferred |
| listen.py docstring | "Milestone 3 … Milestone 4 wraps this in a daemon" | it IS the daemon |
| README "Run it" | mentions talk.py press-to-talk as current | listen.py is the real loop |

**Fix:** add one banner line at the top of each blueprint doc — "⚠️ Historical blueprint; the
implemented system differs, see docs/build/" — rather than rewriting history. Update the
listen.py docstring.

---

## F. Best free upgrades & ideas (ranked by value-for-effort)

1. **Session conversation history (C1)** — biggest intelligence jump, ~20 lines.
2. **Crash-proofing (A2–A5)** — turns a demo into a daily driver, ~30 lines.
3. **Gate hardening (A1 + B1)** — negation-first yes/no + speak the exact command. Safety.
4. **Streamed speech (C5)** — perceived latency cut roughly in half; code already half-exists.
5. **Vision `keep_alive: 0` (D1)** — RAM/heat relief, one line.
6. **Prompt diet (D2)** — faster turns, fewer rate-limit brushes.
7. **compose_email via the user's real Chrome** — they're already logged into their accounts
   there (`https://mail.google.com/mail/u/<N>/?view=cm&…` works in real Chrome); today it opens
   in the separate Playwright profile that needs its own login. Better UX, one line. Keep
   Playwright for *reading/automation*, real Chrome for *user-facing* pages.
8. **Nearby-places tool** — `open_location` already exists; add `search_nearby(query)` using
   the accurate GPS coords (`maps.google.com/search/<query>/@lat,lon,15z`). Trivial and it
   answers the "nearby restaurants" ask properly.
9. **Escalation brain (D5)** — free 120B for hard questions.
10. **Memory consolidation (D3)** — keeps it sharp long-term.
11. **Watch-along video understanding** — BlackHole (already installed) → capture reel/video
    audio → whisper → brain, + a frame via vision. The genuinely new capability on the vision
    list; medium effort, fully local/free.
12. **Speaker verification** — enroll the user's voiceprint (resemblyzer, free) so gated
    actions require *their* voice. Pairs beautifully with the gate. Medium effort.

## G. Suggested order of attack

**Round 1 (make it solid):** A1→A5, B1, C2, C3 — safety + never-crash. 
**Round 2 (make it feel smart):** C1 history, C5 streaming, D2 prompt diet, F7 real-Chrome mail, F8 nearby. 
**Round 3 (make it grow):** D1 vision keep-alive, D3 memory consolidation, F11 watch-along, F12 voiceprint.

Everything above is implementable with what's already installed — **zero new spend**. The 8 GB
ceiling stays respected: online brain remote, one local model at a time, aggressive unloading.
