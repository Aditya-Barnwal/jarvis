# Vision

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [docs/build/](docs/build/).

The goal is a *proper* Jarvis — not a chatbot with a microphone, but an assistant that lives on your machine, knows your context, and can actually *do things* in the world on your behalf.

This document lays out the full ambition, then marks each capability with how real it is today. Honesty here saves you from building toward a wall.

---

## The full ambition

You should be able to say any of these and have Jarvis handle it:

- *"Hey Jarvis, what's on my plate right now?"* → reads your routine/calendar, tells you what to do next.
- *"How am I doing on the quant prep?"* → checks progress across your projects and study plan, gives a real status.
- *"Draft a WhatsApp to Rohan saying I'll be 10 minutes late, and fix my grammar."* → composes it, corrects it, shows you, sends on approval.
- *"How's TCS doing today?"* → pulls the live quote, gives context.
- *"Where did my money go this month?"* → analyzes your expenses, flags the outliers.
- *"Call the electrician."* → places the call through a real telephony path.
- *"Turn off the living room lights."* → controls smart-home devices.
- *"Open my job-copilot and give me the morning briefing."* → talks to your existing tool and narrates.
- Just... *talk to it like a person* — natural back-and-forth, remembers what you said yesterday.

## Reality check: what each of these actually takes

Legend: ✅ straightforward · ⚠️ doable with real constraints · 🔶 possible but risky/limited

| Capability | Reality | The honest note |
|---|---|---|
| Natural conversation, memory | ✅ | This is the core loop + a memory store. Solved by Phases 1–2. |
| Works fully offline | ✅ | Brain falls back to Ollama; all local-data features keep working. See [OFFLINE.md](OFFLINE.md). |
| Learns from you & from the web | ✅ | Accumulates facts/preferences locally; captures web lookups for later. See [LEARNING.md](LEARNING.md). |
| Routine / "what should I do now" | ✅ | You define a routine file + connect your calendar. Jarvis reasons over it. |
| Progress checks across projects | ✅ | Jarvis reads structured status files you (and it) maintain, plus git activity. |
| Notes (incl. from iPhone) | ✅ | Apple Notes syncs iPhone→Mac via iCloud; readable/writable via AppleScript. |
| Reminders (incl. from iPhone) | ✅ | Reminders.app via AppleScript + Jarvis's own proactive nudges. |
| Stock viewing & analysis | ✅ | Free market-data APIs. Live quotes, charts, basic analysis. Not trading. |
| Expense tracking (GPay/UPI) | ✅ | GPay has no export API, but UPI transaction SMS forward to the Mac's `chat.db` and parse locally. Also Takeout / bank CSV. See [capabilities/expenses.md](capabilities/expenses.md). |
| Grammar correction on drafts | ✅ | The brain does this natively. Zero extra infra. |
| Mac control (apps, volume, files) | ✅ | AppleScript / `osascript` + shell. Phase 3. |
| Web browsing & scraping | ✅ | Playwright, run locally. Phase 4. |
| Daily screen time | ⚠️ | Lives in a protected, undocumented `knowledgeC.db`. Works (Mac + iPhone) but fragile across OS updates. See [capabilities/screen-time.md](capabilities/screen-time.md). |
| Smart-home / device control | ⚠️ | Needs Home Assistant or HomeKit bridge. Great once set up; setup is real work. |
| Placing phone calls | ⚠️ | Via Twilio (programmatic, costs per call) or macOS Continuity (through your iPhone). Both work; neither is free-and-instant. |
| Sending SMS | ⚠️ | Twilio, or macOS Messages app via AppleScript (iMessage/SMS relay through iPhone). |
| **WhatsApp automation** | 🔶 | **The big caveat.** Automating your *personal* WhatsApp account violates their terms and risks a ban. Jarvis will **draft + grammar-check + show you**, and you tap send — that's ban-safe. Fully autonomous send is not, and we won't build it. See [docs/capabilities/whatsapp.md](capabilities/whatsapp.md). |
| "Connect to another device/person" | ⚠️ | "Device" = smart-home or SSH into your own machines (✅). "Person" = a call/message to them (⚠️, via the paths above). There's no magic remote-control-of-someone-else's-phone; that doesn't exist and you wouldn't want the security hole. |

## What "do anything I want" realistically means

The architecture is deliberately open-ended: **any capability is just a new tool function** the brain can call. So "anything" is true in the sense that the system is *extensible to* almost anything you can express as code. It is *not* true in the sense that a few specific things (silently botting personal WhatsApp, remote-controlling other people's devices) are blocked by terms-of-service, platform security, or basic ethics — and those blocks are features, not bugs. They're what keep your accounts alive and your setup trustworthy.

The mental shift: you're not waiting for someone to add a feature. You're building a body (the daemon) with a nervous system (tool dispatch), and every new thing you teach it is another muscle. The ceiling is your own time, not the design.

## What we deliberately will NOT build

- Autonomous sending on personal WhatsApp (ban risk).
- Anything that enters your banking/card credentials automatically (you do that yourself, always).
- Auto-submitting job applications or auto-executing trades (human gate, always — same as job-copilot).
- Remote control of devices you don't own.

Everything else on the list is on the table.
