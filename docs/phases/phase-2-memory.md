# Phase 2 — Memory

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**Goal:** Jarvis remembers what you told it yesterday and uses it today. Conversations stop being amnesiac.

Without this, every session starts cold and Jarvis feels like a stranger each time. With it, it feels like it knows you.

---

## What gets stored

Three kinds of memory, all local:

1. **Session summaries** — after each conversation (or on a timer), the brain compresses the exchange into a short summary. Lets Jarvis have continuity without re-sending the entire history every call (which would blow the context window and cost).
2. **Facts & preferences** — durable truths: "gym at 6am", "main focus is quant prep", "prefers short replies", "works at CAMS". These get injected into every brain call.
3. **Entity notes** — people, projects, recurring things. "Rohan = friend", "job-copilot = my local job tool at localhost:8000".

## Storage: SQLite first

You already run SQLite in job-copilot, so no new infra. Schema sketch:

```sql
CREATE TABLE facts (
    id INTEGER PRIMARY KEY,
    key TEXT,            -- e.g. 'routine.gym'
    value TEXT,          -- e.g. '6am daily'
    updated_at TEXT
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    started_at TEXT,
    summary TEXT         -- brain-generated compression of the conversation
);

CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    name TEXT,           -- 'Rohan', 'job-copilot'
    kind TEXT,           -- 'person', 'project'
    notes TEXT
);
```

## How memory reaches the brain

On each turn, before calling the brain, the daemon:

1. Pulls all `facts` (they're small — just dump them).
2. Pulls the last few `session` summaries.
3. Pulls any `entities` mentioned in the current input.
4. Injects them into the system prompt or as a leading context message.

```python
def build_context() -> str:
    facts = get_all_facts()
    recent = get_recent_summaries(n=3)
    return f"What you know about the user:\n{facts}\n\nRecent context:\n{recent}"
```

This is the entire trick behind "it remembers me" — relevant memory as context, every call.

## Writing memory

Two paths:

- **Explicit** — you say "remember that I have a dentist appointment Friday" → the brain calls a `remember(fact)` tool → written to `facts`.
- **Automatic** — at session end, the brain summarizes and extracts any new durable facts, writing them without you asking.

Both use the tool-dispatch pattern from Phase 3, so strictly this phase overlaps a little with Phase 3. You can stub memory writes as direct function calls now and convert them to proper tools once dispatch exists.

## Upgrade path: ChromaDB (later, optional)

Once you have hundreds of facts and summaries, keyword lookup ("what did I say about X") gets weak. ChromaDB adds **semantic** search — embed each memory, retrieve by meaning. Only add it when SQLite lookup visibly fails you. Don't pre-optimize.

## Privacy note

This is the most personal data in the system — your habits, your people, your plans. It lives in a local SQLite file. It is never sent anywhere except as context to the brain (Groq when online) for the current reasoning turn. Keep the `data/` folder git-ignored.

**Ends with:** you tell Jarvis something on Monday, it uses it correctly on Wednesday without being reminded.
