# Capability: Expense analysis

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "Where did my money go this month?", "How much on food?", "Track my GPay spending automatically."

**Reality:** ✅ analysis is clean and fully local. The interesting part is **ingestion** — getting your GPay/UPI spending in. GPay has no personal export or API (a well-known gap), so this doc lays out the realistic paths, with the best automated one first.

Jarvis never logs into your bank or GPay. It reads data that's already on your Mac, or that you export.

---

## The ingestion problem (and the good workaround)

GPay in India deliberately offers **no statement download and no personal transactions API** — the developer API is merchant-only. So "just pull my GPay history" isn't directly possible. But there's a clean automated route for an iPhone + Mac user:

### Path A — Parse UPI transaction SMS from your Mac (recommended, automated)

Every UPI payment triggers a bank SMS ("₹450 debited... UPI ref..."). If you enable **Text Message Forwarding** on your iPhone (Settings → Messages → Text Message Forwarding → your Mac), those SMS land in the Mac's Messages database:

```
~/Library/Messages/chat.db     (SQLite; contains iMessage + forwarded SMS)
```

Jarvis reads that DB (read-only), filters for bank/UPI senders, and extracts amount + merchant + date. This is automated and local — no manual export, works offline.

```python
# src/tools/expenses.py
import sqlite3, os, re
from brain import tool

CHAT_DB = os.path.expanduser("~/Library/Messages/chat.db")
APPLE_EPOCH = 978307200
UPI_SENDERS = ("VM-", "AD-", "VK-", "JM-")   # bank/UPI SMS shortcode prefixes vary

@tool({"name": "ingest_upi_sms",
       "description": "Read recent bank/UPI transaction SMS from the Mac Messages DB and return parsed debits.",
       "parameters": {"type": "object",
           "properties": {"days": {"type": "integer"}},
           "required": []}})
def ingest_upi_sms(days: int = 30):
    con = sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True)
    q = """SELECT text, datetime(date/1000000000 + ?, 'unixepoch') AS ts
           FROM message
           WHERE text IS NOT NULL
             AND date(datetime(date/1000000000 + ?, 'unixepoch')) >= date('now', ?)"""
    rows = con.execute(q, (APPLE_EPOCH, APPLE_EPOCH, f'-{days} day')).fetchall()
    con.close()
    txns = []
    for text, ts in rows:
        m = re.search(r'(?:Rs\.?|INR|₹)\s?([\d,]+\.?\d*)\s+(debited|spent|paid)', text, re.I)
        if m:
            txns.append({"amount": float(m.group(1).replace(",", "")), "ts": ts, "raw": text})
    return {"count": len(txns), "transactions": txns}
```

- Needs **Full Disk Access** (chat.db is protected) — see [../../SETUP.md](../../SETUP.md).
- Needs **Text Message Forwarding** on so bank SMS reach the Mac.
- SMS formats vary by bank, so the regex catches the common shape and the **brain cleans up the rest** — for messy or unusual SMS, Jarvis passes the raw text to the model to extract amount/merchant reliably (no fabrication: if it can't parse, it flags the SMS rather than guessing a number).

### Path B — Google Takeout (periodic, manual, complete)

Google's Takeout export includes your Google Pay activity. Export it (every so often), drop the file in `data/expenses/`, and Jarvis parses it. More complete than SMS (includes merchant names GPay knows), but manual and not real-time.

### Path C — Bank statement CSV/PDF (authoritative)

Export a statement from your bank app/netbanking, drop it in `data/expenses/`. This is the ground truth — every transaction, not just UPI. Best for a proper monthly reconcile. Jarvis parses CSV directly; for PDF it extracts the table.

**Recommendation:** Path A for effortless day-to-day ("what did I spend today?"), Path C monthly for an accurate full picture. Path B if you want GPay's merchant labels without SMS.

## Categorization

1. **Rules** — keyword map for the obvious (`SWIGGY`/`ZOMATO` → food, `UBER`/`OLA` → transport). Fast, deterministic.
2. **Brain fallback** — anything unmatched gets classified by the model from the merchant/SMS string. Learned mappings are saved to the memory DB so it stays consistent and improves (this is the "learn from me" loop — see [../../LEARNING.md](../../LEARNING.md)).

## What Jarvis can tell you

- **Totals & breakdown** — "₹28,400 this month: ₹9,100 food, ₹4,000 transport, …"
- **Trends** — "Food delivery up 40% vs last month."
- **Outliers** — "Biggest single charge: ₹8,000 at [merchant] on the 12th."
- **Budget checks** — if you set budgets in config, "₹2,000 over food with a week left."
- **Daily** — from Path A, "You've spent ₹1,240 today across 4 UPI payments."

## No-fabrication guarantee

Every figure traces to a real SMS row, Takeout entry, or statement line. If an SMS won't parse or a month's data is missing, Jarvis says so instead of estimating — same anti-fabrication discipline as job-copilot.

## Advice vs. information

Jarvis shows where money went and flags patterns. It won't give personalized financial-planning advice (not a licensed advisor). "You spent a lot on delivery" is an observation; "move ₹X into a fund" is advice it stays out of.

## Example

```
You: "Where did my money go this month?"
Jarvis: "₹28,400 total. Food delivery's the big one at ₹9,100 — up sharply from last
         month — then transport ₹4,000 and shopping ₹3,600. Largest single charge was
         ₹8,000 at [merchant] on the 12th. Want the full breakdown or just this week?"
```
