# Capability: Routine & progress

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "What should I do now?", "How's my quant prep going?", "Give me a progress check on everything."

**Reality:** ✅ fully doable and local. This is where Jarvis feels most like a real assistant — it knows your day and your goals and reasons over them.

---

## Two halves

1. **Routine** — "what should I be doing right now" — reasons over your schedule.
2. **Progress** — "how am I tracking on my goals" — reasons over your projects and study plans.

Both run on structured files *you* keep, plus signals Jarvis can read automatically (calendar, git).

## Routine

You define a routine file Jarvis reads:

```yaml
# data/routine.yaml
daily:
  - { time: "06:00", block: "gym" }
  - { time: "09:00-18:00", block: "work (CAMS)" }
  - { time: "20:00-22:00", block: "quant prep / Jarvis build" }
weekly:
  - { day: "Sat", block: "mock interview" }
```

Combined with your **calendar** (Phase 3+ can read Calendar.app via AppleScript, or you connect Google Calendar), Jarvis answers "what now?" by comparing the current time to your routine and calendar:

```python
# src/tools/routine.py
@tool({
    "name": "whats_now",
    "description": "Tell the user what they should be doing now based on routine + calendar.",
    "parameters": {"type": "object", "properties": {}},
})
def whats_now():
    now = datetime.now()
    routine_block = current_block(load_routine(), now)
    calendar = read_calendar(now)          # AppleScript / gcal
    return {"time": now.isoformat(), "routine": routine_block, "calendar": calendar}
```

Jarvis then phrases it naturally: *"It's 8pm — your quant-prep block. Nothing on the calendar until standup at 10 tomorrow. Want to pick up where you left off on Hull chapter 4?"*

## Progress

Progress tracking reads structured status you maintain, so answers are real, not vibes:

- **Projects** — a `STATUS.md` in each project + git commit recency. "job-copilot: last commit 3 days ago, feature X done, Y in progress."
- **Study plans** — a `progress.yaml`:

```yaml
# data/progress.yaml
quant_prep:
  hull_options: { current_chapter: 4, total: 20 }
  sheldon_ross_probability: { current_chapter: 2, total: 12 }
  python_for_finance: { status: "not started" }
  last_session: "2026-06-28"
system_design:
  gaurav_sen: { videos_done: 6 }
  phase: "foundations"
interview_prep:
  leetcode: { tries: "day 1 done", topic: "tries" }
  mock_interviews: 0
```

- **Habits** — routine adherence logged over time (fed by the check-ins in Phase 6).

```python
@tool({
    "name": "progress_check",
    "description": "Report progress across projects, study plans, and habits. Honest, including where the user has stalled.",
    "parameters": {"type": "object",
        "properties": {"area": {"type": "string", "description": "e.g. 'quant', 'everything'"}},
        "required": []},
})
def progress_check(area: str = "everything"):
    return {
        "study": load_progress(),
        "projects": scan_project_status(),   # git recency + STATUS.md
        "habits": routine_adherence(),
    }
```

## The honest-mirror principle

A progress check that only flatters you is useless. Jarvis names slippage: *"Quant prep has stalled — no session in 5 days, still on Hull chapter 4. System design is moving, 6 Gaurav Sen videos in. You've done zero mock interviews so far — that's the gap to close before applications."*

It's encouraging in tone but truthful about the data. No inventing progress that isn't there (no-fabrication rule), and no dismissing real slippage to make you feel good.

## Why this needs *your* upkeep

Jarvis can read git and your calendar automatically, but study-plan progress needs you (or the Phase 6 check-ins) to keep `progress.yaml` current. The trade: five seconds of "Jarvis, mark Hull chapter 4 done" keeps every future progress check accurate. The check-in feature in [../phases/phase-6-proactive.md](../phases/phase-6-proactive.md) automates most of this by asking you and logging the answers.

## Example

```
You: "How's everything going?"
Jarvis: "Mixed. System design's on track — 6 videos into foundations. Quant prep
         has stalled, no session in 5 days, still on Hull ch.4. Job-copilot's
         active, 3 new matches overnight. The real gap: zero mock interviews yet.
         Want to slot one in this Saturday?"
```
