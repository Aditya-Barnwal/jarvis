"""Where the user is, dynamically — so it's right wherever they go.
GPS (macOS Location Services via CoreLocationCLI) → saved location → IP.
GPS needs a one-time grant: System Settings → Privacy → Location Services → CoreLocationCLI."""
import subprocess

from brain import tool


def _reverse_geocode(coords: str) -> str:
    """coords 'lat,lon' -> readable place, via free OpenStreetMap Nominatim."""
    try:
        import json
        import urllib.request
        lat, lon = coords.split(",")
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=14"
        req = urllib.request.Request(url, headers={"User-Agent": "jarvis-assistant"})
        with urllib.request.urlopen(req, timeout=6) as r:
            a = json.load(r).get("address", {})
        parts = [a.get(k) for k in ("suburb", "city_district", "city", "town", "state")]
        return ", ".join(p for p in dict.fromkeys(parts) if p) or ""
    except Exception:
        return ""


_CACHE: dict = {}   # 5-min location cache — GPS costs seconds, don't pay it per call


def current_location() -> dict:
    """Best-effort current location. Returns {coords?, place?, source}. Uses the Mac's
    GPS/Wi-Fi location (CoreLocationCLI) first — accurate and updates as you move.
    Cached for 5 minutes so back-to-back tools (weather, nearby) don't re-pay GPS."""
    import time as _t
    if _CACHE and _t.time() - _CACHE.get("at", 0) < 300:
        return _CACHE["loc"]
    loc = _current_location_uncached()
    _CACHE.update(at=_t.time(), loc=loc)
    return loc


def _current_location_uncached() -> dict:
    try:
        out = subprocess.run(
            ["CoreLocationCLI", "-once", "yes", "-format", "%latitude %longitude"],
            capture_output=True, text=True, timeout=6).stdout.strip()
        parts = out.replace(",", " ").split()   # CoreLocationCLI outputs space-separated
        if len(parts) >= 2 and "❌" not in out and "disabled" not in out.lower():
            coords = f"{parts[0]},{parts[1]}"
            # Coords are accurate; the geocoded NAME is coarse (admin zone), so prefer a
            # user-stated area name for display if we have one. Coords stay authoritative
            # for nearby searches (see docs/build/ISSUES.md).
            name = None
            try:
                import memory
                name = memory.recall("location")
            except Exception:
                pass
            return {"coords": coords, "place": name or _reverse_geocode(coords),
                    "name_is_approx": name is None, "source": "gps"}
    except Exception:
        pass
    try:
        import memory
        saved = memory.recall("location")
        if saved:
            return {"place": saved, "source": "saved"}
    except Exception:
        pass
    return {"source": "ip"}   # callers (e.g. weather) fall back to IP geolocation


@tool({"name": "get_location",
       "description": "Get the user's current location (GPS if available, else last known / IP).",
       "parameters": {"type": "object", "properties": {}}})
def get_location():
    loc = current_location()
    return {"location": loc.get("place") or loc.get("coords") or "unknown",
            "source": loc["source"]}


@tool({"name": "search_nearby",
       "description": "Find places near the user right now (restaurants, cafes, ATMs, "
                      "pharmacies, landmarks…) — opens Google Maps centred on their ACTUAL "
                      "GPS coordinates in Chrome.",
       "parameters": {"type": "object",
           "properties": {"query": {"type": "string",
               "description": "what to find, e.g. 'restaurants', 'chemist', 'petrol pump'"}},
           "required": ["query"]}})
def search_nearby(query: str):
    import urllib.parse
    loc = current_location()
    coords = loc.get("coords")
    if coords:
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}/@{coords},15z"
    else:   # no GPS — let Maps use its own location guess
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(query + ' near me')}"
    r = subprocess.run(["open", "-a", "Google Chrome", url], capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(["open", url])
    return {"opened_maps_for": query, "centred_on": loc.get("place") or coords or "Maps' guess",
            "accuracy_note": "centred on real coordinates" if coords else "IP-level only"}
