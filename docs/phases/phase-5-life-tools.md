# Phase 5 — Life tools

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**Goal:** the capabilities that make Jarvis *yours* — stocks, expenses, routine/progress, messaging with grammar. Each is a tool module built on the Phase 3 dispatch pattern.

Because dispatch already exists, these are independent. Build them in any order, one per evening. Each has its own detailed spec in [../capabilities/](../capabilities/).

---

## The modules

| Module | What you say | Spec |
|---|---|---|
| Stocks | "how's TCS doing", "show me the Nifty" | [capabilities/stocks.md](../capabilities/stocks.md) |
| Expenses | "where did my money go this month" | [capabilities/expenses.md](../capabilities/expenses.md) |
| Routine & progress | "what should I do now", "how's my quant prep going" | [capabilities/routine-and-progress.md](../capabilities/routine-and-progress.md) |
| Messaging + grammar | "draft a WhatsApp to Rohan and fix the grammar" | [capabilities/whatsapp.md](../capabilities/whatsapp.md), [capabilities/grammar.md](../capabilities/grammar.md) |
| Calls & SMS | "text Mom I'll call later", "call the electrician" | [capabilities/calls-and-messaging.md](../capabilities/calls-and-messaging.md) |
| Notes | "note that...", "what did I note about..." | [capabilities/notes.md](../capabilities/notes.md) |
| Reminders | "remind me to...", "what's due today" | [capabilities/reminders.md](../capabilities/reminders.md) |
| Screen Time | "how much screen time yesterday" | [capabilities/screen-time.md](../capabilities/screen-time.md) |

## Shared shape

Every life-tool module follows the same structure, so once you've built one, the rest are muscle memory:

```
src/tools/<capability>.py
├── one or more @tool-decorated functions
├── each returns structured data (never a guess — no-fabrication rule)
└── side-effectful ones (send/spend) wrapped in the confirmation gate
```

## Data sources at a glance

- **Stocks** — free market-data APIs (quotes, history). Read-only. No trading.
- **Expenses** — UPI transaction SMS from the Mac's `chat.db` (auto, local), or a CSV/Takeout export you drop in. Never logs into your bank.
- **Routine/progress** — a `routine.yaml` you maintain + your calendar + git activity + project status files. Jarvis reasons over them.
- **Notes/Reminders** — Apple Notes.app / Reminders.app via AppleScript; sync from your iPhone through iCloud.
- **Screen Time** — local `knowledgeC.db` (Mac + iPhone usage); read-only.
- **Messaging** — drafts locally; sends only through ban-safe, human-approved paths.

Most of these read **local data**, which is why they keep working offline — see [../../OFFLINE.md](../../OFFLINE.md). Several need Full Disk Access or Automation permission (one-time) — see [../../SETUP.md](../../SETUP.md).

## The honesty line, restated

Two things on this list have real constraints, and the specs are blunt about them:

- **WhatsApp** — Jarvis drafts and grammar-checks; *you* tap send. Autonomous personal-account sending is a ban risk we don't build. See the spec.
- **Calls** — need a real telephony path (Twilio, paid) or your paired iPhone (Continuity). Not free-and-instant, but real.

Everything else here is clean and fully local.

**Ends with:** the daily-driver features — money, markets, routine, messages — all answerable by voice.
