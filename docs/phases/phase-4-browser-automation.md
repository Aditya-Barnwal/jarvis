# Phase 4 — Browser automation

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**Goal:** Jarvis can search the web, read pages, and fill forms — run locally via Playwright, with a human gate on anything that writes.

This is what makes the "if internet is there, it can look things up and give proper answers" half of the Iron Man vision real.

---

## Playwright, run locally

Playwright drives a real browser (Chromium/WebKit) from Python. It runs entirely on your machine — there is no cloud remote-control connector, and you don't want one (it'd be a security hole). Local Playwright is a self-hosted setup you fully control.

```bash
pip install playwright
playwright install chromium
```

## Tools this phase adds

| Tool | Does | Side effect? |
|---|---|---|
| `web_search` | query a search engine, return top results | no (read) |
| `read_page` | fetch a URL, extract main text | no (read) |
| `fill_form` | fill fields on a page | **yes → gated** |
| `click` | click a control | **yes → gated** |

Read tools run freely. Write tools (fill, click, submit) route through the confirmation gate — Jarvis shows/says what it's about to do and waits for your yes.

```python
# src/tools/browser.py
from playwright.sync_api import sync_playwright

@tool({
    "name": "read_page",
    "description": "Fetch a web page and return its main text content.",
    "parameters": {"type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"]},
})
def read_page(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=15000)
        text = page.inner_text("body")
        browser.close()
    return {"url": url, "text": text[:5000]}
```

## Offline behavior

When there's no internet, these tools skip gracefully with a spoken note ("I can't reach the web right now") instead of hanging. The daemon checks connectivity before dispatching a web tool.

## The read-vs-write line

This phase is where "ban-safe" and "human-in-the-loop" earn their keep:

- **Reading** public pages is fine and unlimited.
- **Writing** (logging into sites, submitting forms, posting) is gated behind your explicit confirmation, and we never automate anything that violates a site's terms in a ban-triggering way. No consumer-site scraping at volume, no credential-stuffing, no auto-submitting applications (job-copilot already taught this lesson).

## Careful: don't rebuild a scraper farm

The temptation is to point Playwright at everything. Resist. Use it for genuine "look this up for me" moments and legitimate form-filling *you* approve. Bulk scraping gets IPs blocked and accounts banned — exactly what the ban-safe principle exists to prevent.

**Ends with:** "look up the weather in Chennai and tell me", "read this article and summarize it", "check if this site is up" all work, and Jarvis answers real-world questions it couldn't from memory alone.
