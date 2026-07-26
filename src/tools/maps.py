"""Distance & travel time — answered BY VOICE, not "go check a map".

Free stack: OpenStreetMap Nominatim geocodes the destination (biased near the
user), the public OSRM router computes driving distance/time. If the place
can't be found (or was misheard), it says so honestly so the user can correct.
"""
import json
import re
import subprocess
import urllib.parse
import urllib.request

from brain import sanitizer, tool
from tools.location import current_location

_UA = {"User-Agent": "jarvis-assistant"}


def _remember_place(name: str) -> None:
    """Keep a rolling vocabulary of places the user actually asks about — fed to
    whisper as a decode hint so 'Pind' is HEARD correctly next time, first try."""
    try:
        import memory
        known = [p.strip() for p in (memory.recall("known_places") or "").split(",") if p.strip()]
        short = name.split(",")[0].strip()[:40]
        if short and short.lower() not in (k.lower() for k in known):
            known = (known + [short])[-10:]
            memory.remember("known_places", ", ".join(known))
    except Exception:
        pass


@sanitizer("get_distance")
def _clean_destination(args: dict, user_text: str) -> dict:
    """Reconstruct what the user MEANT: 'PIND restaurant P-I-N-D' -> 'PIND
    restaurant'; strip correction phrases ('I meant', 'named', 'called')."""
    d = (args.get("destination") or "").strip()
    d = re.sub(r"\b(?:i\s+meant|the\s+restaurant\s+named|named|called)\b", " ", d, flags=re.I)
    d = re.sub(r"\b(?:[a-zA-Z][\-\s]){2,}[a-zA-Z]\b", " ", d)   # drop spelled-out runs
    d = re.sub(r"\s{2,}", " ", d).strip(" ,.-")
    return {**args, "destination": d or args.get("destination", "")}


def _get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


def _geocode_near(query: str, lat: str, lon: str):
    """Find a place, preferring hits near the user (viewbox-bounded first)."""
    base = "https://nominatim.openstreetmap.org/search?format=json&limit=1&q="
    dl = 0.25  # ~25km box around the user
    box = (f"&viewbox={float(lon)-dl},{float(lat)+dl},{float(lon)+dl},{float(lat)-dl}"
           "&bounded=1")
    for url in (base + urllib.parse.quote(query) + box,
                base + urllib.parse.quote(query)):          # fallback: anywhere
        hits = _get(url)
        if hits:
            return hits[0]
    return None


def _google_find(query: str, lat: str, lon: str):
    """PRIMARY geocoder: Google Maps (far better Indian POI coverage than OSM).
    Free path — our own browser opens a Maps search biased to the user's spot and
    reads the matched place's coordinates out of the result URL (!3d..!4d..).
    Returns (name, lat, lon) or None."""
    import re as _re
    try:
        # HEADLESS, self-contained browser: no visible window, far lighter on RAM
        # (the headed shared context competed with Kokoro for memory during the
        # speak path), and fully closed before we return.
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True, args=["--mute-audio"])
            try:
                # 17z first = "nearest to the user"; 13z retry = wider net.
                for zoom in ("17z", "13z"):
                    page = b.new_page()
                    try:
                        page.goto(
                            f"https://www.google.com/maps/search/"
                            f"{urllib.parse.quote(query)}/@{lat},{lon},{zoom}",
                            timeout=20000, wait_until="domcontentloaded")
                        page.wait_for_timeout(2500)
                        m = _re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", page.url)
                        if not m:   # results list → open the top hit
                            first = page.query_selector("a[href*='/maps/place/']")
                            if first:
                                first.click()
                                page.wait_for_timeout(2500)
                                m = _re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", page.url)
                        # Never fall back to map-centre coords — that's the user's
                        # own position from the URL ("at your current location" bug).
                        name = (page.title() or query).replace(" - Google Maps", "").strip()
                        if m and name and name.lower() != "google maps":
                            if abs(float(m.group(1)) - float(lat)) < 0.0005 and \
                                    abs(float(m.group(2)) - float(lon)) < 0.0005:
                                continue   # "found" the user themselves — bad parse
                            return name, m.group(1), m.group(2)
                    finally:
                        page.close()
            finally:
                b.close()
    except Exception:
        return None
    return None


@tool({"name": "get_distance",
       "description": "Distance and driving time from the user's current location to a "
                      "destination (a place, restaurant, area, landmark…). Answers directly — "
                      "use for 'how far is X' / 'distance to X' / 'how long to reach X'.",
       "parameters": {"type": "object",
           "properties": {"destination": {"type": "string"}},
           "required": ["destination"]}})
def get_distance(destination: str):
    loc = current_location()
    if not loc.get("coords"):
        return {"error": "couldn't determine your current location"}
    lat, lon = loc["coords"].split(",")

    # PRIMARY: Google Maps (accurate local POIs — finds the Pind 200m away, not
    # a namesake 6km off). Backup: OSM/Nominatim variants.
    g = _google_find(destination, lat, lon)
    if g:
        name, dlat, dlon = g
        route = _get(f"https://router.project-osrm.org/route/v1/driving/"
                     f"{lon},{lat};{dlon},{dlat}?overview=false")
        if route.get("routes"):
            r = route["routes"][0]
            _remember_place(name)
            out = {"destination_found": name,
                   "from": loc.get("place") or "your current location",
                   "distance_km": round(r["distance"] / 1000, 1),
                   "driving_minutes": round(r["duration"] / 60),
                   "source": "google maps"}
            # Fuzzy search can land on a DIFFERENT place than asked ("SNDAS tech
            # park" → "Techno Park", 2km away). ALWAYS disclose the matched name —
            # it's how the user catches a wrong match.
            import difflib
            sim = difflib.SequenceMatcher(
                None, destination.lower(), name.lower()).ratio()
            out["instruction"] = (f"You MUST say the matched place name '{name}' in "
                                  "your answer, e.g. \"{name} is X km away\".")
            if sim < 0.5:
                out["instruction"] += (" The name differs a lot from what the user "
                                       "said — also ASK if that's the place they meant.")
            return out

    city = (loc.get("place") or "").split(",")[-1].strip()
    variants = [destination, f"{destination} {city}",
                re.sub(r"\brestaurant\b", "", destination, flags=re.I).strip()]
    hit = None
    for q in dict.fromkeys(v for v in variants if v):
        hit = _geocode_near(q, lat, lon)
        if hit:
            break
    if not hit:
        # OSM doesn't list it (common for Indian restaurants/shops) — fall back to
        # Google Maps, which does: open the route so the user still gets the answer.
        gurl = ("https://www.google.com/maps/dir/?api=1"
                f"&origin={lat},{lon}&destination={urllib.parse.quote(destination)}")
        r = subprocess.run(["open", "-a", "Google Chrome", gurl],
                           capture_output=True, text=True)
        if r.returncode != 0:
            subprocess.run(["open", gurl])
        return {"fallback": "OpenStreetMap doesn't list this place. Opened the route to "
                            f"'{destination}' in Google Maps — the distance and time are "
                            "shown there. Tell the user this plainly."}

    dlat, dlon = hit["lat"], hit["lon"]
    route = _get(f"https://router.project-osrm.org/route/v1/driving/"
                 f"{lon},{lat};{dlon},{dlat}?overview=false")
    if not route.get("routes"):
        return {"error": "found the place but couldn't compute a road route"}
    r = route["routes"][0]
    found = hit.get("display_name", destination).split(",")[0]
    _remember_place(found)
    return {
        "destination_found": found,
        "from": loc.get("place") or "your current location",
        "distance_km": round(r["distance"] / 1000, 1),
        "driving_minutes": round(r["duration"] / 60),
    }
