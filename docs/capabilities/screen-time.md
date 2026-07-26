# Capability: Screen Time

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "How much screen time did I get yesterday?", "What am I spending too long on?" — for both Mac and iPhone.

**Reality:** ⚠️ doable and genuinely useful, but the **fragile** one. The data sits in a protected, undocumented Apple SQLite database. It works, and people build exactly this, but treat the schema as something that can shift between macOS versions.

---

## Where the data lives

macOS records app usage in a local SQLite DB:

```
~/Library/Application Support/Knowledge/knowledgeC.db
```

The useful table is `ZOBJECT` where `ZSTREAMNAME = '/app/usage'`. Crucially, **if your iPhone shares Screen Time across devices (iCloud), your phone's usage syncs into this same database** — so one query covers Mac *and* iPhone. (iPhone data may also arrive via `~/Library/Biome/` protobuf files; a helper like `aw-import-screentime` parses those if the knowledgeC path is thin.)

## Reading it

```python
# src/tools/screentime.py
import sqlite3, os
from brain import tool

DB = os.path.expanduser("~/Library/Application Support/Knowledge/knowledgeC.db")
APPLE_EPOCH = 978307200   # seconds between 2001-01-01 and 1970-01-01

@tool({"name": "screen_time",
       "description": "Report app usage (minutes) for a given day. day_offset 0=today, 1=yesterday.",
       "parameters": {"type": "object",
           "properties": {"day_offset": {"type": "integer"}},
           "required": []}})
def screen_time(day_offset: int = 1):
    q = """
    SELECT ZVALUESTRING AS app,
           SUM(ZENDDATE - ZSTARTDATE)/60.0 AS minutes
    FROM ZOBJECT
    WHERE ZSTREAMNAME = '/app/usage'
      AND date(datetime(ZSTARTDATE + ?, 'unixepoch')) = date('now', ?)
    GROUP BY ZVALUESTRING
    ORDER BY minutes DESC
    """
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(q, (APPLE_EPOCH, f'-{day_offset} day')).fetchall()
    con.close()
    return {"day_offset": day_offset,
            "apps": [{"app": a, "minutes": round(m, 1)} for a, m in rows]}
```

Note the Apple "Cocoa" timestamp quirk: times are seconds since 2001-01-01, so you add `978307200` to convert to Unix time. Open the DB **read-only** — never write to it.

## The catch: Full Disk Access + a moving schema

Two honest warnings:

1. **Full Disk Access required.** `knowledgeC.db` is protected. The process running Jarvis (your terminal, or the daemon's launchd job, i.e. `/bin/bash`) needs Full Disk Access granted in System Settings → Privacy & Security. Without it you get "operation not permitted." See [../../SETUP.md](../../SETUP.md).
2. **Undocumented, version-dependent schema.** Apple doesn't publish this schema and has changed the surrounding storage before (there are several candidate DBs across macOS versions — `knowledgeC.db`, `CoreDuetData.db`, `RMAdminStore-Local.sqlite`). The query above is the current common path, but if an OS update breaks it, expect to adjust the table/column names. Build it so a failure here degrades gracefully ("I can't read Screen Time right now") rather than crashing the daemon.

This is the one capability where I'd say: great when it works, but don't make anything critical depend on it. It's a "nice insight", not load-bearing.

## What Jarvis can tell you

- "Yesterday: 5h 20m total. Top three: Safari 1h50, Instagram 1h10, Xcode 55m."
- Trends over time (store daily snapshots in the memory DB and compare): "Instagram's up 40% this week."
- Tie into progress/routine: "You logged 2 hours on social yesterday and zero on quant prep — want to flip that today?"

## Privacy

This is sensitive behavioural data. It stays local, read-only, and is only summarized back to you. It's never sent anywhere except as context to the brain for the current turn (Groq online / Ollama offline), same rule as everything else.

## Example

```
You: "How was my screen time yesterday?"
Jarvis: "5 hours 20 minutes across Mac and phone. Biggest was Safari at nearly 2 hours,
         then Instagram at just over an hour. Social's been creeping up this week —
         want me to set a nudge?"
```
