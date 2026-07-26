# Known issues & limitations (living list)

Kept updated as we go. Severity: 🔴 blocks a feature · 🟠 degrades UX · 🟡 minor/edge.
Last updated: 2026-07-18 (post-polish pass).

> ✅ **Polish pass fixes (2026-07-18):** vision model now evicted from RAM right after
> `see_screen` (no 3 GB lingering); `compare_prices`/Gmail flows open in the user's real
> Chrome; daemon logs truncate on install; conversation follow-ups now carry session
> history; the daemon survives brain/STT/voice/mic errors instead of crashing; gated
> actions are negation-safe and stated verbatim by the system. Remaining items below.

## 🔴 / 🟠 The 8 GB RAM ceiling (root cause of most pain)

The M1 Air has **8 GB RAM** and is already swap-heavy. You cannot hold the offline 7B brain
+ Kokoro + Whisper + a vision model warm at once.

- **Voice was laggy/broken offline** (🟠): running Ollama `qwen2.5:7b` (~5 GB) + Kokoro caused
  swap → ~45s synth + glitchy audio. **Mitigation**: run the brain on **Groq** (0 local RAM)
  when online — that freed the RAM and fixed it. Offline is inherently constrained.
- **Vision is slow** (🟠): `see_screen` first call ~**155s** to load `qwen2.5vl:3b` (~3 GB) on
  8 GB. Works, reads on-screen text well, but heavy. **Mitigation**: model loads on-demand and
  unloads when idle; keep expectations low for the first call after idle.
- **Deep sleep** (mitigation): after `JARVIS_SLEEP_AFTER` idle seconds the voice model is
  unloaded to reclaim RAM; reloads ~3.5s on wake.
- **Heat** is a RAM/swap symptom, not disk — closing Electron apps + using Groq helps.

## 🟠 Audio / Bluetooth

- **Bluetooth earphones cause "channeling"/warbly voice + worse mic** (🟠): when the mic is
  used, macOS switches BT headphones to low-quality HFP (call) mode, then back to A2DP — the
  switching *is* the distortion, and it also makes STT mishear. **Fix**: use **wired earphones
  or the laptop mic/speakers**. Not a code bug — a macOS+Bluetooth limitation.
- **Live mic degrades speaker quality** (mitigated): a live mic drops macOS speakers into
  comms mode. Fixed by releasing the mic while speaking (barge-in `off`, default). Cost: ~0.4s
  reopen between turns.

## 🟠 Speech-to-text accuracy

- Misheard a lot in wind/on a terrace with BT earphones ("Chennai"→"enchantment"). **Mitigation**:
  upgraded whisper `base.en` → **`small.en`**. Still imperfect in noise + BT mic (see above).

## 🟠 GPS / location — coords work, NAME is coarse

- **Parse bug fixed** (2026-07-18): CoreLocationCLI outputs coords space-separated; code now
  parses correctly. GPS via `CoreLocationCLI` works (needs Location Services granted once).
- **Two real accuracy limits remain:**
  1. **Mac has no GPS chip** — location is **Wi-Fi/IP-based**, so the point can be off by a few
     hundred m to ~1 km (worse indoors / on VPN). Fine-ish outdoors, not survey-grade.
  2. **Reverse-geocode names are coarse** (🟠): OpenStreetMap/Nominatim returns the *administrative
     zone* ("Zone 15 Sholinganallur", ~7 km from the actual spot's local name) instead of the
     neighbourhood ("Thoraipakkam"). OSM has no finer local tag at these coords in India.
- **Impact**: the *coordinates* are good enough for **"nearby restaurants/landmarks"** IF those
  searches use the **raw lat,long** (Google Maps `search?q=restaurants&ll=<lat,lon>`), NOT the
  fuzzy name. So build location features off coords, not the geocoded name.
- **For pinpoint accuracy / correct local names**: use the **iPhone's real GPS** (via Continuity/
  a Shortcut) or a better geocoder (Google's, in India), or let the user confirm their area.
  TODO. IP fallback is worst (guessed "Namakkal" for a Chennai user).

## 🟡 Web / shopping

- **`compare_prices` extraction is unreliable** (🟡): Google Shopping blocks headless scraping
  (0 results). Headed real browser works better; as a guaranteed fallback it **opens the
  comparison in Chrome** so the user sees all prices. A dedicated aggregator (Smartprix/BuyHatke)
  would be more parseable — TODO.
- `web_search` (DuckDuckGo) captchas in **headless** mode; use headed (the default).

## 🟡 Brain / tool-calling

- Groq **`llama-3.3-70b` was flaky** at tools (emitted malformed `<function=…>` text, false
  positives, occasional 400 crash). **Fixed** by switching to `gpt-oss-20b` + a text-format
  fallback parser + a `tool_use_failed` retry.
- Offline **`llama3.2:3b` routes tools at ~29%** (false tool-fires on plain conversation).
  **Fixed** by defaulting offline to `qwen2.5:7b` (~95%).

## 🟢 Fixed in the post-test hotfix round (2026-07-18, evening)

- **"What's the weather" opened a browser** (routing regression from the prompt diet):
  explicit ROUTING rules restored + a code-level **argument sanitizer** (model kept inventing
  city="London" — now a city is honoured only if the user actually said it).
- **Weather switched wttr.in → Open-Meteo** (free, no key): reliable, ~2s, and returns
  today+tomorrow, which powers the "and tomorrow?" follow-up with real data.
- **GPS cached 5 min** (was re-paying up to 12s per tool call); CoreLocationCLI timeout 12→6s.
- **Playwright window closes after each use** (no lingering "Chrome for Testing" window).
- **Blind "Done." after tool-loop exhaustion** → replaced with a real one-line outcome.
- **Cross-session conversation memory**: every exchange logged; sessions summarized on
  sleep/exit (by the brain when online) and injected into future context — Jarvis now
  remembers what you talked about YESTERDAY, not just this session.
- **Mid-flight ABORT**: confirmed installs/commands run in the background; saying
  "stop"/"abort" kills the process group (verified: killed a 30s command in 1.5s).
- **Startup ~3× faster to "Ready"**: voice warms in a background thread.

## 🟢 Wake-cue / first-turn-hang round (2026-07-18, night)

- **First reply hung 30s+ with text shown but no voice**: the reply was ready in 2.3s but
  speaking waited on the background Kokoro cold-load, which crawls under whisper/CPU
  contention. Fixes: warmup starts FIRST (before wake/VAD load), Kokoro loading is now
  lock-protected (a warmup+synth race could double-load the model = swap storm), and the
  wait is visible ("voice model still warming — one moment…"). Fastest cure remains the
  always-warm login daemon.
- **No audible sign of life on wake**: two-stage listen — speak in one breath and he catches
  it directly; say just "Hey Jarvis" and pause ~1.4s and he answers "Sir?" (Friday: "Boss?").
- **Follow-up window 6s → 120s** (`JARVIS_FOLLOWUP_WINDOW`).

## 🟢 Distance/POI accuracy round (2026-07-18, late night)

- **get_distance found a namesake 6.7 km away instead of the Pind 200m from home**: OSM's
  Indian POI coverage is patchy AND prominence-ranked matches beat nearby ones. Fix:
  **Google Maps is now the primary geocoder** (free — our browser reads the matched place's
  coordinates out of the Maps URL; no paid API), searched **nearest-first** (17z viewport,
  then 13z wider), then OSRM computes the road distance. Verified: 'Pind restaurant' →
  'PIND Thoraipakkam', 0.4 km / 1 min. OSM stays as backup; final fallback opens the route
  in Chrome. Note: ~8s per lookup (browser scrape) vs ~2s OSM — accuracy over speed here.
- **TTS number reading** ('6 000 km' → 'six zero zero zero k m'): speech normalizer joins
  thin-spaced digits and expands units (km, °C, ₹, %).
- **Spelled corrections** ('P-I-N-D') now reconstructed by prompt rule + code sanitizer;
  whisper gets the recent exchange as a decode hint so repeated names stay consistent.

## 🟢 Distance polish (2026-07-19, final round)

- **"7.5" spoken as "seven five"** → speech normalizer now says "seven point five".
- **Wrong-place answers without disclosure** ("SNDAS tech park" silently matched
  "Techno Park" 2km away): distance replies now ALWAYS state the matched place name,
  and ask "is that the one you meant?" when the match diverges from the query.
- "Voice a little laggy": the `[trace] speak:` number includes full playback time —
  actual voice-start delay is ~1–2s after the text prints. Deeper cure = login daemon
  (warm models) + RAM headroom (close heavy apps).

## 🟢 THE stall, root-caused and killed (2026-07-19)

- Step tracing caught it red-handed: `[ears] mic close wedged` → the per-turn mic
  close hung in CoreAudio, and the abandoned zombie stream then poisoned the reopen —
  `resume()` blocked forever on a device the dead handle still held.
- **Design fix, not a patch: the mic is never closed mid-session anymore.** One
  callback-fed stream for the whole session; "pause" is a software gate (frames
  discarded while Jarvis speaks), "resume" re-enables it. Zero PortAudio state
  transitions per turn → nothing left to wedge. Measured: pause 0ms, resume 89ms
  (was 3s wedge + hang), stable across rapid cycles.
- Trade-off accepted: the input device stays active during playback, which macOS may
  answer with slightly reduced speaker quality — cosmetic, vs stalls which were fatal.
  If voice quality audibly drops, revisit (e.g. gate + device-release only for long replies).

## 🟢 Speech-hang postmortem (2026-07-19)

- **Reply printed but never spoken; daemon stuck** — pattern: right after a distance
  lookup. Mechanism: the Maps lookup launches Chromium, whose audio service touches
  CoreAudio around our playback; `sd.wait()` then blocked forever (no timeout).
  Fixes: (1) **playback watchdog** — we know the clip length, never wait longer
  (side-benefit: `stop()` now interrupts mid-sentence in <1s); (2) Chromium launched
  with `--mute-audio` so its audio service stays away from the device.
- Same round: noise annotations '(wind blowing)' filtered; whisper hint now uses
  ONLY user words (assistant text in the hint caused hallucinated replies under fan
  noise); known-places vocabulary biases STT; self-echo guard.

## 🟡 Miscellaneous / TODO

- **`list_reminders` can be slow (~30s) with many reminders** — AppleScript iterates the
  whole Reminders DB. Fine for occasional use; optimize (single list / EventKit) if it annoys.

- **Conversation follow-up mode**: built, needs more real-world verification.
- **Weather with a "City, Region" string** (e.g. "Thoraipakkam, Chennai") can return empty from
  wttr.in — coordinate/geocoding edge; single city names work.
- **Chatterbox voice-cloning engine**: adapter written but dormant (torch/numpy conflict — needs
  an isolated venv).
- **Deferred features** (see `../../CLAUDE`-style memory / ROADMAP): live-dictation email,
  watch-along video understanding (record+transcribe via BlackHole), nearby-device scan,
  wardrobe/stylist, speaker recognition, tutor mode, Chrome multi-account.
