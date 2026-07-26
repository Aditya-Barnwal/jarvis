# Capability: WhatsApp

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "Draft a WhatsApp to Rohan saying I'll be late, fix my grammar, and send it."

**What we build:** everything up to *and including showing you the polished message* — Jarvis drafts, corrects grammar, and puts it one tap from sending. The final send is done the ban-safe way.

This is the most important honesty note in the whole project, so read it fully.

---

## Why not fully autonomous send?

Automating a **personal** WhatsApp account — driving WhatsApp Web with a bot, sending without a human — violates WhatsApp's Terms of Service and is a well-known way to get your number **banned**. That's not a hypothetical; WhatsApp actively detects and bans automated personal accounts. Losing your primary number is a catastrophic failure mode, and it directly violates this project's ban-safe principle.

So we don't build silent autonomous send on your personal account. Here's what we build instead — all of which is genuinely useful.

## The three ban-safe paths

### Path A — Draft + grammar + one-tap (recommended default)

Jarvis composes the message, runs it through grammar correction (the brain does this natively — see [grammar.md](grammar.md)), and hands it to you ready to send:

- **Clipboard hand-off:** Jarvis copies the polished text to your clipboard and opens the WhatsApp chat. You paste and hit send. Two taps.
- **Deep link:** Jarvis opens `https://wa.me/<number>?text=<url-encoded-message>` which launches WhatsApp with the message pre-filled in the right chat. You tap send.

```python
# src/tools/whatsapp.py
import urllib.parse, subprocess

@tool({
    "name": "whatsapp_draft",
    "description": "Compose a WhatsApp message and open the chat with it pre-filled for the user to send.",
    "parameters": {"type": "object",
        "properties": {
            "number": {"type": "string", "description": "recipient in intl format, e.g. 9198..."},
            "message": {"type": "string"}},
        "required": ["number", "message"]},
})
def whatsapp_draft(number: str, message: str):
    url = f"https://wa.me/{number}?text={urllib.parse.quote(message)}"
    subprocess.run(["open", url])          # opens WhatsApp with text pre-filled
    return {"opened": True, "message": message}
```

This is the sweet spot: Jarvis does 95% of the work (understanding intent, drafting, fixing grammar, opening the right chat), you do the one deliberate tap that keeps your account safe. It *feels* like Jarvis sent it.

### Path B — macOS keystroke assist (semi-auto, still you-in-control)

Using the WhatsApp desktop app + macOS accessibility, Jarvis can type into the focused chat via AppleScript keystrokes. Still gated: it types, you review on screen, you press enter. This blurs toward automation, so keep the human confirm — never let it press enter itself on personal chats.

### Path C — Official WhatsApp Business Cloud API (legit programmatic send)

If you genuinely need *automated* sending, the only sanctioned route is the **WhatsApp Business Cloud API**. It's real and unbannable-when-used-right, but:

- It's for **business** messaging, not your personal number.
- Requires a Meta Business account, a registered business phone number, and approval.
- Session messaging is free-ish within a 24-hour window; template messages outside it are paid.
- Overkill for "text my friend I'll be late."

Use this only if you later want Jarvis to send legitimate business/transactional messages. For personal chats, Path A is the answer.

## Grammar checking (the part that's 100% clean)

The "recommend grammar if it checks" ask is trivially safe and built-in: before any draft is handed off, the brain reviews it and returns a corrected version plus a note on what changed. No extra infra, no risk. Full detail in [grammar.md](grammar.md).

```
You: "WhatsApp Rohan: hey i will be reaching there in 10 min is that okay"
Jarvis (drafts + corrects): "Hey Rohan, I'll be there in 10 minutes — is that okay?"
         "Opened the chat with that ready to send. Want any changes?"
```

## The bottom line

- ✅ Draft, understand intent, fix grammar, open the right chat pre-filled — fully built.
- ✅ One-tap send by you — ban-safe, feels seamless.
- 🔶 Silent autonomous personal send — **not built**, because it gets your number banned.
- ⚠️ Real automated send — only via the Business Cloud API, only if you actually need it.

You lose almost nothing in daily feel, and you keep your WhatsApp account alive. That's the right trade.
