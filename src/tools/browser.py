"""Browser automation via Playwright — Jarvis's web hands.

Read tools (read_page, web_search) run freely. WRITE actions (fill/click/send)
will route through a human confirmation gate — never auto-submitting anything,
never entering credentials for you. Runs a real Chromium locally with a
PERSISTENT profile (data/browser), so once you log into Gmail there, it stays
logged in for later sessions.
"""
import os
import re
import subprocess
import urllib.parse

from brain import tool

_PROFILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "browser")
_HEADLESS = os.getenv("JARVIS_BROWSER_HEADLESS", "0") == "1"

_pw = None
_ctx = None


def _context():
    """Lazily launch (once) a persistent Chromium context and reuse it."""
    global _pw, _ctx
    if _ctx is None:
        from playwright.sync_api import sync_playwright
        os.makedirs(_PROFILE, exist_ok=True)
        os.chmod(_PROFILE, 0o700)      # session cookies live here — owner-only
        _pw = sync_playwright().start()
        # --mute-audio: keep Chromium's audio service away from the output device —
        # its init/teardown around our playback can wedge CoreAudio (voice hangs).
        _ctx = _pw.chromium.launch_persistent_context(
            _PROFILE, headless=_HEADLESS, args=["--mute-audio"])
    return _ctx


def shutdown():
    global _pw, _ctx
    try:
        if _ctx:
            _ctx.close()
        if _pw:
            _pw.stop()
    finally:
        _ctx = _pw = None


@tool({"name": "read_page",
       "description": "Open a web page and return its main visible text. Read-only.",
       "parameters": {"type": "object",
           "properties": {"url": {"type": "string"}}, "required": ["url"]}})
def read_page(url: str):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    page = _context().new_page()
    try:
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
        text = page.inner_text("body")
        title = page.title()
    finally:
        page.close()
        shutdown()      # close the visible browser window — no lingering "Chrome for Testing"
    return {"url": url, "title": title, "text": text[:4000]}


@tool({"name": "web_search",
       "description": "Search the web and return the top results (title + link + snippet). Read-only.",
       "parameters": {"type": "object",
           "properties": {"query": {"type": "string"}}, "required": ["query"]}})
def web_search(query: str):
    page = _context().new_page()
    try:
        page.goto("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query),
                  timeout=20000, wait_until="domcontentloaded")
        results = []
        for r in page.query_selector_all(".result")[:5]:
            a = r.query_selector(".result__a")
            snip = r.query_selector(".result__snippet")
            if a:
                results.append({"title": a.inner_text().strip(),
                                "url": _clean(a.get_attribute("href")),
                                "snippet": snip.inner_text().strip() if snip else ""})
    finally:
        page.close()
        shutdown()      # close the visible browser window
    return {"query": query, "results": results}


def _clean(href: str) -> str:
    """Unwrap DuckDuckGo's /l/?uddg= redirect to the real destination URL."""
    if href and "uddg=" in href:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if q.get("uddg"):
            return urllib.parse.unquote(q["uddg"][0])
    return href


def _price_num(p: str) -> int:
    return int(re.sub(r"[^\d]", "", p) or 0)


@tool({"name": "compare_prices",
       "description": "Compare prices for a product across shopping sites (uses Google "
                      "Shopping, which aggregates sellers like Amazon/Flipkart). Returns the "
                      "cheapest options and opens the full comparison in the browser.",
       "parameters": {"type": "object",
           "properties": {"product": {"type": "string"}}, "required": ["product"]}})
def compare_prices(product: str):
    q = urllib.parse.quote(product)
    page = _context().new_page()
    items = []
    try:
        page.goto(f"https://www.google.com/search?tbm=shop&q={q}&gl=in&hl=en",
                  wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(1500)
        for sel in ("div.sh-dgr__content", "div.sh-dlr__list-result", "div.KZmu8e"):
            for c in page.query_selector_all(sel)[:10]:
                txt = c.inner_text()
                m = re.search(r"₹\s?[\d,]+", txt)
                if m:
                    items.append({"item": txt.split("\n")[0][:70].strip(),
                                  "price": m.group(0).replace(" ", ""),
                                  "where": next((ln for ln in txt.split("\n")
                                                 if "₹" not in ln and len(ln) > 2), "")[:40]})
            if items:
                break
        items.sort(key=lambda x: _price_num(x["price"]))
    finally:
        page.close()
        shutdown()      # close the visible browser window
    # Open the full comparison in the user's real Chrome so they can see everything.
    subprocess.run(["open", "-a", "Google Chrome",
                    f"https://www.google.com/search?tbm=shop&q={q}"])
    return {"product": product, "cheapest": items[:5],
            "note": "Opened the full price comparison in Chrome."}


def _open_in_chrome(url: str):
    """User-facing pages open in the user's REAL Chrome (already logged into their
    Google accounts), foregrounded. Playwright stays for reading/automation only."""
    r = subprocess.run(["open", "-a", "Google Chrome", url], capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(["open", url])


@tool({"name": "open_gmail",
       "description": "Open Gmail in the user's Chrome. account = Google account index "
                      "(0 = first account, 1 = second, …).",
       "parameters": {"type": "object",
           "properties": {"account": {"type": "integer"}}}})
def open_gmail(account: int = 0):
    _open_in_chrome(f"https://mail.google.com/mail/u/{account}/")
    return {"opened": True, "account": account}


@tool({"name": "compose_email",
       "description": "Open a Gmail compose window in the user's Chrome, pre-filled with "
                      "recipient, subject and body on the chosen account (0=first, 1=second), "
                      "ready for the user to review and SEND themselves (never auto-sent).",
       "parameters": {"type": "object",
           "properties": {
               "to": {"type": "string", "description": "recipient email"},
               "subject": {"type": "string"},
               "body": {"type": "string"},
               "account": {"type": "integer", "description": "Google account index (0=first)"}},
           "required": ["to", "subject", "body"]}})
def compose_email(to: str, subject: str, body: str, account: int = 0):
    q = urllib.parse.urlencode({"view": "cm", "fs": "1", "to": to, "su": subject, "body": body})
    _open_in_chrome(f"https://mail.google.com/mail/u/{account}/?{q}")
    return {"opened": True, "to": to, "subject": subject,
            "note": "Draft is open in Chrome, pre-filled — review it and press Send."}
