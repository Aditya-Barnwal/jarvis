"""Mac control — Jarvis's hands on the machine. AppleScript/shell actions.
First use of app control prompts for Automation permission (one-time)."""
import difflib
import glob
import os
import subprocess
import urllib.parse

from brain import tool


def _osa(script: str) -> str:
    return subprocess.run(["osascript", "-e", script],
                          capture_output=True, text=True).stdout.strip()


def _installed_apps() -> dict:
    """Map app display-name -> .app path, across the real app locations
    (includes Brave/Chrome PWAs like 'byoutube' in ~/Applications)."""
    patterns = [
        "/Applications/*.app", "/Applications/*/*.app", "/System/Applications/*.app",
        os.path.expanduser("~/Applications/**/*.app"),
    ]
    apps = {}
    for pat in patterns:
        for p in glob.glob(pat, recursive=True):
            apps[os.path.splitext(os.path.basename(p))[0]] = p
    return apps


def _find_app(query: str):
    """Fuzzy-find an installed app by name. Returns (name, path) or (None, None)."""
    apps = _installed_apps()
    ql = query.strip().lower()
    for name in apps:                                   # exact
        if name.lower() == ql:
            return name, apps[name]
    subs = [n for n in apps if ql in n.lower() or n.lower() in ql]  # contains (byoutube⊇youtube)
    if subs:
        best = min(subs, key=len)
        return best, apps[best]
    close = difflib.get_close_matches(query, list(apps), n=1, cutoff=0.6)  # typo-tolerant
    if close:
        return close[0], apps[close[0]]
    return None, None


@tool({"name": "list_apps",
       "description": "List the applications installed on the Mac (to find one by name).",
       "parameters": {"type": "object", "properties": {}}})
def list_apps():
    return {"apps": sorted(_installed_apps())}


@tool({"name": "control_volume",
       "description": "Set the Mac output volume, 0 (mute) to 100.",
       "parameters": {"type": "object",
           "properties": {"level": {"type": "integer"}}, "required": ["level"]}})
def control_volume(level: int):
    level = max(0, min(100, int(level)))
    _osa(f"set volume output volume {level}")
    return {"volume": level}


@tool({"name": "open_app",
       "description": "Open an installed app by name — fuzzy-matched against the real app "
                      "library (so 'youtube' finds a 'byoutube' app). If NO matching app is "
                      "installed, it returns an error — then use open_website if it's a site, "
                      "or ask the user for the app's exact name.",
       "parameters": {"type": "object",
           "properties": {"name": {"type": "string"}}, "required": ["name"]}})
def open_app(name: str):
    match, path = _find_app(name)
    if not match:
        return {"error": f"no app matching '{name}' is installed",
                "hint": "It may be a website (use open_website), or tell me the app's exact name."}
    r = subprocess.run(["open", path], capture_output=True, text=True)
    if r.returncode != 0:
        return {"error": f"couldn't open '{match}'", "detail": r.stderr.strip()[:80]}
    return {"opened": match}


_SITES = {"youtube": "https://youtube.com", "gmail": "https://mail.google.com",
          "maps": "https://maps.google.com", "whatsapp": "https://web.whatsapp.com",
          "chatgpt": "https://chatgpt.com", "github": "https://github.com"}


@tool({"name": "open_website",
       "description": "Open a website in the default browser by name or URL (e.g. 'youtube', "
                      "'gmail', 'espn.com'). Use this for sites like YouTube that aren't apps.",
       "parameters": {"type": "object",
           "properties": {"site": {"type": "string"}}, "required": ["site"]}})
def open_website(site: str):
    s = site.strip().lower()
    if s in _SITES:
        url = _SITES[s]
    elif s.startswith(("http://", "https://")):
        url = site
    elif "." in s:
        url = "https://" + s
    else:
        url = f"https://{s}.com"
    # Open in the user's real Chrome (their logged-in accounts) and bring it to front.
    r = subprocess.run(["open", "-a", "Google Chrome", url], capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(["open", url])   # fall back to default browser
    return {"opened": url, "foreground": True}


@tool({"name": "open_location",
       "description": "Open a place/address in Google Maps (e.g. a restaurant, an area). "
                      "If no place is given, uses the user's saved location.",
       "parameters": {"type": "object",
           "properties": {"place": {"type": "string"}}}})
def open_location(place: str = ""):
    if not place:
        try:
            import memory
            place = memory.recall("location") or ""
        except Exception:
            pass
    url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place)}"
    r = subprocess.run(["open", "-a", "Google Chrome", url], capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(["open", url])
    return {"opened_map_for": place or "your area"}


@tool({"name": "quit_app",
       "description": "Quit / close a macOS application by name.",
       "parameters": {"type": "object",
           "properties": {"name": {"type": "string"}}, "required": ["name"]}})
def quit_app(name: str):
    _osa(f'tell application "{name}" to quit')
    return {"quit": name}


@tool({"name": "media_control",
       "description": "Control music playback: play, pause, next, or previous (Spotify/Apple Music).",
       "parameters": {"type": "object",
           "properties": {"action": {"type": "string",
               "enum": ["play", "pause", "next", "previous"]}},
           "required": ["action"]}})
def media_control(action: str):
    for app in ("Spotify", "Music"):
        if _osa(f'tell application "System Events" to (name of processes) contains "{app}"') != "true":
            continue
        if action in ("play", "pause"):
            _osa(f'tell application "{app}" to {action}')
        elif action == "next":
            _osa(f'tell application "{app}" to next track')
        elif action == "previous":
            _osa(f'tell application "{app}" to previous track')
        return {"app": app, "action": action}
    return {"error": "no music app is running"}


@tool({"name": "set_clipboard",
       "description": "Copy text to the Mac clipboard.",
       "parameters": {"type": "object",
           "properties": {"text": {"type": "string"}}, "required": ["text"]}})
def set_clipboard(text: str):
    subprocess.run(["pbcopy"], input=text, text=True)
    return {"copied_chars": len(text)}
