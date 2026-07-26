"""Weather via Open-Meteo — free, no API key, fast and reliable (wttr.in kept
flaking). Uses the user's cached GPS coords when no city is given; geocodes a
named city via Open-Meteo's geocoding API. Fails honestly offline."""
import json
import urllib.parse
import urllib.request

from brain import sanitizer, tool


@sanitizer("get_weather")
def _only_cities_the_user_said(args: dict, user_text: str) -> dict:
    """gpt-oss keeps inventing city='London' for no-city questions. Enforce in
    code: keep a city only if the user actually said it; otherwise use their
    real location. (Also drops non-places like 'here'.)"""
    city = (args.get("city") or "").strip()
    if city and (city.lower() not in user_text.lower()
                 or city.lower() in {"here", "outside", "my location", "current location"}):
        return {**args, "city": ""}
    return args

_WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
        45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
        61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
        71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
        80: "light showers", 81: "showers", 82: "heavy showers",
        95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "jarvis-assistant"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


@tool({"name": "get_weather",
       "description": "Get current weather (and today's range). If no city is given, uses "
                      "the user's current location automatically — 'what's the weather' just works.",
       "parameters": {"type": "object",
           "properties": {"city": {"type": "string", "description": "optional; omit for here"}}}})
def get_weather(city: str = ""):
    try:
        where = city
        if city:
            g = _get("https://geocoding-api.open-meteo.com/v1/search?count=1&name="
                     + urllib.parse.quote(city))
            hit = (g.get("results") or [{}])[0]
            lat, lon = hit.get("latitude"), hit.get("longitude")
            where = hit.get("name") or city
            if lat is None:
                return {"error": f"couldn't find a place called '{city}'"}
        else:
            from tools.location import current_location
            loc = current_location()
            if loc.get("coords"):
                lat, lon = loc["coords"].split(",")
                where = loc.get("place") or "your location"
            else:
                return {"error": "couldn't determine your location — tell me the city"}

        w = _get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                 "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
                 "weather_code&daily=temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max&timezone=auto&forecast_days=2")
        cur, day = w["current"], w["daily"]
        return {
            "location": where,
            "temp_c": cur["temperature_2m"],
            "feels_like_c": cur["apparent_temperature"],
            "humidity_pct": cur["relative_humidity_2m"],
            "conditions": _WMO.get(cur["weather_code"], "unknown"),
            "today": {"max_c": day["temperature_2m_max"][0], "min_c": day["temperature_2m_min"][0],
                      "rain_chance_pct": day["precipitation_probability_max"][0]},
            "tomorrow": {"max_c": day["temperature_2m_max"][1], "min_c": day["temperature_2m_min"][1],
                         "rain_chance_pct": day["precipitation_probability_max"][1]},
        }
    except Exception as e:
        return {"error": f"couldn't reach the weather service ({type(e).__name__})"}
