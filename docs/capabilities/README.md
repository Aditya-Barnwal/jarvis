# Capabilities

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

One spec per thing Jarvis can do. Each maps a natural request to how it's actually built, with honest notes on constraints.

Legend: ✅ clean & local · ⚠️ real constraints · 🔶 risky, built the safe way

| Capability | Reality | Spec |
|---|---|---|
| Grammar & writing help | ✅ | [grammar.md](grammar.md) |
| Stocks & markets | ✅ | [stocks.md](stocks.md) |
| Expense analysis (GPay/UPI) | ✅ | [expenses.md](expenses.md) |
| Routine & progress | ✅ | [routine-and-progress.md](routine-and-progress.md) |
| Notes (Apple Notes) | ✅ | [notes.md](notes.md) |
| Reminders | ✅ | [reminders.md](reminders.md) |
| Screen Time | ⚠️ | [screen-time.md](screen-time.md) |
| Calls & messaging | ⚠️ | [calls-and-messaging.md](calls-and-messaging.md) |
| WhatsApp | 🔶 | [whatsapp.md](whatsapp.md) |

Every capability is a **tool module** (`src/tools/<name>.py`) built on the dispatch pattern from [../phases/phase-3-mac-control.md](../phases/phase-3-mac-control.md). Once Phase 3 is done, these are independent — build them in any order.

## Two cross-cutting docs

- **[../../OFFLINE.md](../../OFFLINE.md)** — which of these work with no internet (most of them do — they read local data).
- **[../../LEARNING.md](../../LEARNING.md)** — how Jarvis accumulates knowledge from you and from the web, so it gets more useful over time.

## The rules that shape all of these

1. **No fabrication** — every number/fact Jarvis reports traces to real data. Empty source → it says so.
2. **Human gate on side effects** — anything that sends, spends, or deletes waits for your explicit yes.
3. **Local-first** — capabilities read data already on your Mac (via Full Disk Access / Automation permissions) rather than cloud logins. This is why they work offline.

## Data these read (all local)

| Source | Feeds | Permission |
|---|---|---|
| `chat.db` (Messages) | expense SMS, message drafts | Full Disk Access |
| `knowledgeC.db` | screen time | Full Disk Access |
| Notes.app / Reminders.app | notes, reminders | Automation |
| `data/*.csv`, `data/*.yaml` | expenses, routine, progress | none (your files) |
| SQLite memory store | learned facts, preferences | none (local) |

## Adding your own

Write a function in `src/tools/`, decorate it as a tool with a JSON schema, and it's live. That's the whole extension story — see the dispatch section in the Phase 3 doc.
