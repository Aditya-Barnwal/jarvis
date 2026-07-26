"""Screen vision — Jarvis sees what's on your screen. Screenshot -> a local
vision model (Ollama) -> answer. Covers 'what's on my screen', a photo, a reel,
a video frame, reading text on screen, etc.

Needs: Screen Recording permission (first use prompts) + a vision model pulled
in Ollama (e.g. `ollama pull moondream` or `llava`). Model via JARVIS_VISION_MODEL.
"""
import base64
import os
import subprocess
import tempfile

from openai import OpenAI

import config
from brain import tool

VISION_MODEL = os.getenv("JARVIS_VISION_MODEL", "qwen2.5vl:3b")
_SHOT = os.path.join(tempfile.gettempdir(), "jarvis_screen.png")


@tool({"name": "see_screen",
       "description": "Look at what's currently on the user's screen (a photo, a reel/video "
                      "frame, a web page, any app) and answer a question about it. Use for "
                      "'what am I looking at', 'what does this say', 'explain this', 'what's "
                      "in this picture/reel'.",
       "parameters": {"type": "object",
           "properties": {"question": {"type": "string",
               "description": "what the user wants to know about the screen"}}}})
def see_screen(question: str = ""):
    subprocess.run(["screencapture", "-x", _SHOT], check=False)
    if not os.path.exists(_SHOT):
        return {"error": "couldn't capture the screen (grant Screen Recording permission)"}
    subprocess.run(["sips", "-Z", "1280", _SHOT], capture_output=True)  # downscale for the model
    try:
        b64 = base64.b64encode(open(_SHOT, "rb").read()).decode()
        client = OpenAI(base_url=config.OLLAMA_BASE_URL, api_key="ollama")
        r = client.chat.completions.create(
            model=VISION_MODEL, max_tokens=300,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": question or "Describe what's on the screen."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
        return {"seen": r.choices[0].message.content.strip()}
    except Exception as e:
        return {"error": f"vision model unavailable ({type(e).__name__}). "
                         f"Pull one: 'ollama pull {VISION_MODEL}'."}
    finally:
        _unload_model()               # free ~3GB immediately (8GB machine!)
        try:
            os.remove(_SHOT)          # privacy: never keep the screenshot
        except OSError:
            pass


def _unload_model() -> None:
    """Tell Ollama to evict the vision model NOW instead of its default ~5min
    keep-alive — on 8GB, 3GB lingering causes swap/heat (see docs/build/ANALYSIS.md D1)."""
    try:
        import json
        import urllib.request
        base = config.OLLAMA_BASE_URL.rsplit("/v1", 1)[0]
        req = urllib.request.Request(
            f"{base}/api/generate",
            data=json.dumps({"model": VISION_MODEL, "keep_alive": 0}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass                          # eviction is best-effort
