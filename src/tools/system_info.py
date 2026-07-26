"""Simple factual tools so Jarvis can answer from real data, not guesses.
The brain has no clock/sensors, so these need tools — otherwise it (correctly)
says it doesn't know rather than fabricating."""
import re
import subprocess
from datetime import datetime

from brain import tool


@tool({"name": "get_time",
       "description": "Get the current local date and time. Use for 'what time is it', "
                      "'what's the date', 'what day is it'.",
       "parameters": {"type": "object", "properties": {}}})
def get_time():
    now = datetime.now()
    return {
        "time": now.strftime("%I:%M %p").lstrip("0"),
        "day": now.strftime("%A"),
        "date": now.strftime("%d %B %Y"),
    }


@tool({"name": "get_battery",
       "description": "Get the Mac's battery percentage and whether it's charging.",
       "parameters": {"type": "object", "properties": {}}})
def get_battery():
    out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    pct = re.search(r"(\d+)%", out)
    return {
        "percent": int(pct.group(1)) if pct else None,
        "charging": ("AC Power" in out) or ("charging" in out.lower()),
        "source": "AC" if "AC Power" in out else "battery",
    }
