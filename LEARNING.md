# Learning

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [docs/build/](docs/build/).

"It should learn from the internet and from me." Jarvis does this two ways, and they feed the same place: a **local knowledge store** that makes Jarvis smarter over time and works offline afterward.

The key idea: learning = **capture something once, recall it forever** — without re-fetching, and without you repeating yourself.

---

## Two sources, one memory

```
   YOU                          THE INTERNET
   "I go to the gym at 6am"      "What's the RBI repo rate?"
   "Call my mom Anjali"          a doc you asked it to read
   corrections you make          a fact it looked up
        │                              │
        ▼                              ▼
   ┌─────────────────────────────────────────┐
   │        LOCAL KNOWLEDGE STORE             │
   │   facts · preferences · entities ·       │
   │   learned snippets (SQLite / Chroma)     │
   └─────────────────────────────────────────┘
        │
        ▼
   injected as context into every brain call
   → Jarvis "knows" it next time, even offline
```

## Learning from you (works offline)

This is the memory system from [docs/phases/phase-2-memory.md](docs/phases/phase-2-memory.md), used as a learning loop:

- **Explicit teaching** — "remember that I prefer trains over flights", "my manager is Priya" → stored as a fact/entity.
- **Corrections** — when you correct Jarvis ("no, my gym is at 6, not 7"), it overwrites the old fact. It learns from being wrong.
- **Passive extraction** — at the end of a conversation, the brain pulls out durable facts worth keeping ("mentioned starting Hull chapter 5") and stores them, so you don't have to spell everything out.

Over weeks this builds a real model of your life: people, habits, preferences, projects. All local, all private, all available offline.

## Learning from the internet (capture online, recall offline)

When Jarvis looks something up — via Groq's built-in web search or Playwright ([docs/phases/phase-4-browser-automation.md](docs/phases/phase-4-browser-automation.md)) — it can **persist what it found** so the knowledge survives past that one query:

- You ask "what's the current repo rate?" → Jarvis searches, answers, and stores the fact with a timestamp. Ask again offline next week and it recalls it (noting how old it is).
- "Read this article and remember the key points" → the summary goes into the knowledge store, tagged, searchable later.
- "Learn how our company's leave policy works from this page" → captured once, answerable forever.

```python
# src/tools/learn.py
@tool({"name": "remember_fact",
       "description": "Store a fact (from the user or the web) in long-term memory with a source and timestamp.",
       "parameters": {"type": "object",
           "properties": {
               "fact": {"type": "string"},
               "source": {"type": "string", "description": "'user' or a URL"},
               "topic": {"type": "string"}},
           "required": ["fact", "source"]}})
def remember_fact(fact: str, source: str, topic: str = "general"):
    store_fact(fact=fact, source=source, topic=topic, ts=now())
    return {"stored": True}
```

## Staleness: learned facts aren't forever-true

A fact learned from the web has a timestamp and a source. Jarvis is honest about age: "The repo rate was 6.25% when I checked three weeks ago — want me to refresh that now that you're online?" This keeps the no-fabrication rule intact: it never presents a stale cached fact as if it were live.

## Optional: a real knowledge base (RAG)

For "learn from documents" at scale — your notes, PDFs, saved articles — the upgrade is ChromaDB as a vector store. Jarvis embeds each captured snippet; on a later question it retrieves the relevant ones by meaning and answers from them. This is standard retrieval-augmented generation, running entirely locally:

- Ingest: chunk → embed (a local sentence-transformers model, same family you use in job-copilot) → store in Chroma.
- Recall: embed the question → nearest-neighbour search → feed hits to the brain as context.

Because both the embeddings and the store are local, **this whole "learned knowledge" system works offline** once things are captured. Start with SQLite facts; add Chroma when you want semantic recall over a growing pile of learned material.

## What "learning" does NOT mean here

To be precise and avoid overpromising: Jarvis is **not** fine-tuning or retraining a model on your data. "Learning" here means **accumulating and retrieving knowledge** — the model weights don't change; the *context* it's given gets richer. That's the right design for a personal assistant: it's transparent (you can read/edit every stored fact), private (nothing leaves the machine), reversible (delete a fact and it's gone), and it works with any brain backend. True weight-level personalization is possible in principle but is a different, heavier project with little practical upside here.
