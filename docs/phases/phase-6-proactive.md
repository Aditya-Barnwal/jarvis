# Phase 6 — Proactive + integrations

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**Goal:** Jarvis stops only reacting and starts *initiating*. Morning briefings, progress nudges, scheduled check-ins, and integration with job-copilot.

This is the phase that makes it feel like a real Jarvis rather than a voice command line.

---

## From reactive to proactive

Everything so far waits for the wake word. Now the daemon also runs **scheduled triggers** that let Jarvis speak first:

- A morning briefing at a set time.
- A gym reminder before 6am.
- A nudge if you haven't touched a project in N days.
- An evening progress check.

Implementation: an `asyncio` scheduler inside the daemon (or `launchd` timers that poke the daemon). At each trigger, Jarvis assembles context and either speaks or queues a spoken message for when it detects you're at the machine.

```python
# src/proactive.py — sketch
async def scheduler(jarvis):
    while True:
        now = datetime.now()
        if now.hour == 7 and not briefed_today():
            await jarvis.speak(build_morning_briefing())
            mark_briefed()
        await asyncio.sleep(60)
```

## The morning briefing

The showcase feature. It pulls from everything:

```
"Good morning. Here's your day:
 - job-copilot: 19 companies indexed, 3 new matches overnight, top fit is a
   backend role at 82%.
 - Calendar: standup at 10, gym blocked at 6pm.
 - Markets: Nifty flat, TCS down 0.6%.
 - Quant prep: you're on Hull chapter 4, 2 days since last session.
 - Expenses: ₹4,200 spent this week, mostly food delivery.
 Want details on any of these?"
```

Every line is real data from a tool, assembled by the brain into natural speech. No fabrication — if a source is empty, it says so.

## job-copilot integration

job-copilot already runs as a local FastAPI service at `localhost:8000`. Jarvis integrates by calling its REST API — read-only, no auto-submit (job-copilot's own human-approval gate stays in force).

```python
# src/tools/job_copilot.py
import requests

@tool({
    "name": "job_status",
    "description": "Get job-copilot status: counts and top new matches.",
    "parameters": {"type": "object", "properties": {}},
})
def job_status():
    r = requests.get("http://localhost:8000/api/status", timeout=5)
    return r.json()   # feeds straight into the briefing
```

If job-copilot exposes match/company endpoints, Jarvis can surface "top 3 new matches" in the briefing and offer to open the tool.

## Progress checks

"How's everything going?" becomes a real answer by reading structured status:

- **Projects** — git commit recency, a `STATUS.md` per project you keep current.
- **Study plans** — a `progress.yaml` tracking where you are (Hull chapter, LeetCode topics, mock interviews done).
- **Habits** — routine adherence from the routine module.

Jarvis reasons over these and gives an honest read, including calling out where you've stalled. (It won't flatter you — a real progress check names the slippage.)

## Scheduled check-ins

Optional gentle accountability: an evening "did you do the gym / study block today?" that logs your answer into progress tracking, so the data stays current without manual bookkeeping.

**Ends with:** an unprompted, accurate morning briefing and honest progress reads — the moment Jarvis feels less like a tool and more like an assistant that's actually paying attention.
