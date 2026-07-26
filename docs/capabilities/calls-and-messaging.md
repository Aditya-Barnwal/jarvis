# Capability: Calls & messaging

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "Text Mom I'll call her later", "Call the electrician", "Connect me to [person]."

**Reality:** ⚠️ doable, but needs a real telephony path. There's no magic — a phone call or SMS has to go through *something*. Here are the real options, honestly costed.

---

## The core truth

"Call a person" or "connect to another device" isn't a software trick — it needs a channel to the phone network. Two legitimate routes:

## Route 1 — macOS Continuity (free, needs your iPhone nearby)

If you have an iPhone paired to the Mac (same Apple ID, Continuity on), the Mac can place calls and send iMessage/SMS *through* your phone. Jarvis drives this via AppleScript against Messages.app and the calling handoff.

```python
# src/tools/messaging.py
import subprocess

@tool({
    "name": "send_imessage",
    "description": "Send an iMessage/SMS via the paired iPhone through Messages.app. Gated: confirm before sending.",
    "parameters": {"type": "object",
        "properties": {"recipient": {"type": "string"}, "message": {"type": "string"}},
        "required": ["recipient", "message"]},
})
def send_imessage(recipient: str, message: str):
    script = f'''
    tell application "Messages"
        send "{message}" to buddy "{recipient}" of (service 1 whose service type is iMessage)
    end tell
    '''
    subprocess.run(["osascript", "-e", script])
    return {"sent": True, "to": recipient}
```

- **Calls:** macOS can hand a call to your iPhone (`tel:` links / FaceTime). Jarvis initiates; the call rings on your phone. You're still holding the phone for the actual conversation.
- **Cost:** free (uses your existing plan).
- **Constraint:** iPhone must be nearby and on the same network/Apple ID.
- **Gate:** sending is a side effect → confirmation required before it fires.

## Route 2 — Twilio (paid, fully programmatic, phone-independent)

Twilio gives Jarvis real, standalone SMS and voice — no phone needed nearby.

```python
# src/tools/twilio_tools.py
from twilio.rest import Client
client = Client(SID, TOKEN)   # from .env

@tool({
    "name": "send_sms",
    "description": "Send an SMS via Twilio. Gated: confirm before sending.",
    "parameters": {"type": "object",
        "properties": {"to": {"type": "string"}, "body": {"type": "string"}},
        "required": ["to", "body"]},
})
def send_sms(to: str, body: str):
    msg = client.messages.create(to=to, from_=TWILIO_NUMBER, body=body)
    return {"sid": msg.sid, "to": to}
```

- **Calls:** Twilio can dial a number and play text-to-speech, or bridge you in. Real programmatic calling.
- **Cost:** per SMS / per minute (cheap, but not free). Needs a Twilio number.
- **Constraint:** setup (account, number, verified caller ID for some flows). Indian regulations (DLT registration) apply for SMS to Indian numbers — worth knowing before you rely on it.
- **Gate:** same confirmation gate; also, spending money → doubly gated.

## "Connect to another device"

Two honest interpretations:

- **Your own devices** — SSH into your other machines, control smart-home gear (via Home Assistant/HomeKit), AirPlay to speakers. All ✅ once set up. Jarvis running a command on your home server is a normal tool call.
- **Someone else's device/phone** — remote-controlling another person's device does not exist as a legitimate capability and would be a serious security/privacy violation. Not built, by design. "Connecting to a person" means calling or messaging them (Routes 1/2), not taking over their device.

## The confirmation gate (mandatory here)

Every send and every call is irreversible and can cost money or reach a real human. So all of these route through the gate:

```
You: "Text Rohan I'll be 10 minutes late."
Jarvis: "I'll send 'Hi Rohan, I'll be 10 minutes late' to Rohan via iMessage. Confirm?"
You: "Yes."
Jarvis: [sends] "Done."
```

No silent sends, ever. This is the same human-in-the-loop discipline as the rest of the project.

## Recommendation

Start with **Route 1 (Continuity)** — free, and for a personal assistant on your own Mac with your iPhone around, it covers "text Mom", "call the electrician" fine. Add **Twilio** only if you want phone-independent or automated messaging later. Both live behind the same `messaging` tool interface, so Jarvis picks based on what's available.
