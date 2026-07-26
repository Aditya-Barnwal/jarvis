"""The brain: Groq online, Ollama offline — one OpenAI-compatible code path.

Both Groq and Ollama speak the OpenAI chat API, so we use the same `openai`
client for both and only swap base_url + model. This is the single code path
the architecture docs promise; tool dispatch (Phase 3) hangs off `run_turn`.
"""
import json
import re

from openai import OpenAI

from config import (
    GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, GROQ_MODEL_SMART,
    OLLAMA_BASE_URL, OLLAMA_MODEL, SYSTEM_PROMPT, has_groq_key,
)
from connectivity import is_online

# --- Tool registry (used now as plain callables; full dispatch lands Phase 3) -
TOOLS: dict[str, callable] = {}     # name -> python callable
TOOL_SCHEMAS: list[dict] = []       # OpenAI-style function schemas the model sees


def tool(spec: dict):
    """Register a function as a brain-callable tool. `spec` = the OpenAI function
    schema ({"name","description","parameters"}). Phase 3 dispatches these; for
    now they're also directly callable functions."""
    def wrap(fn):
        TOOLS[spec["name"]] = fn
        TOOL_SCHEMAS.append({"type": "function", "function": spec})
        return fn
    return wrap


# --- Confirmation gate: consequential tools (install, run shell, delete) don't
# execute until the user says yes. The gated call is held in PENDING; the voice
# loop asks for confirmation and runs it on approval.
GATED: set[str] = set()
PENDING = None


def gate(*names: str) -> None:
    GATED.update(names)


# Per-tool argument sanitizers: fn(args, user_text) -> args. Lets a tool enforce
# rules in CODE that the model keeps breaking in prompt (e.g. inventing a city
# for get_weather when the user never named one).
SANITIZERS: dict[str, callable] = {}


def sanitizer(tool_name: str):
    def wrap(fn):
        SANITIZERS[tool_name] = fn
        return fn
    return wrap


def _sanitize(name: str, args: dict, user_text: str) -> dict:
    fn = SANITIZERS.get(name)
    if fn:
        try:
            return fn(args, user_text)
        except Exception:
            pass
    return args


def _dispatch(name: str, fn, args: dict):
    """Run a tool, or hold it for confirmation if it's gated."""
    global PENDING
    if name in GATED:
        if PENDING is not None and PENDING != {"name": name, "args": args}:
            # Never silently replace one held action with another — the user could
            # end up confirming something different from what was described.
            return {"error": "another action is already awaiting confirmation; "
                             "resolve that one first"}
        PENDING = {"name": name, "args": args}
        return {"status": "confirmation_required",
                "instruction": "Do NOT claim it's done. Ask the user to confirm. The system "
                               "will state the exact action to them itself."}
    if fn is None:
        return {"error": "unknown tool"}
    try:
        return fn(**args)
    except Exception as e:
        return {"error": str(e)}


def describe_pending() -> str:
    """The exact held action, stated by the SYSTEM (never the model — a paraphrase
    could be deceptive if a web page prompt-injected the request)."""
    if not PENDING:
        return ""
    name, args = PENDING["name"], PENDING["args"]
    if name == "run_command":
        return f"run the command: {args.get('command', '?')}"
    if name == "install_app":
        return f"install: {args.get('name', '?')}"
    detail = ", ".join(f"{k} {v}" for k, v in args.items())
    return f"{name.replace('_', ' ')}: {detail}" if detail else name.replace("_", " ")


def confirm_pending():
    """Execute the held gated action (called by the voice loop on 'yes')."""
    global PENDING
    if not PENDING:
        return None
    action, PENDING = PENDING, None
    fn = TOOLS.get(action["name"])
    try:
        return {"ran": action["name"], "result": fn(**action["args"]) if fn else "unknown tool"}
    except Exception as e:
        return {"ran": action["name"], "error": str(e)}


def cancel_pending():
    global PENDING
    PENDING = None


def use_groq() -> bool:
    """Use Groq only when we have a key AND a network. Otherwise Ollama."""
    return has_groq_key() and is_online()


def get_client():
    """Return (client, model, label) for whichever brain is active."""
    if use_groq():
        return OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL), GROQ_MODEL, "groq"
    # Ollama needs no real key; the client just wants a non-empty string.
    return OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL), OLLAMA_MODEL, "ollama"


def ask(text: str, system: str = SYSTEM_PROMPT) -> str:
    """Single-shot question -> spoken reply. No tools yet (that's Phase 3)."""
    client, model, _ = get_client()
    resp = client.chat.completions.create(
        model=model,
        max_tokens=300,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
    )
    return resp.choices[0].message.content.strip()


def stream_reply(text: str, system: str = SYSTEM_PROMPT):
    """Yield reply tokens as they arrive, so the voice can start speaking on the
    first completed sentence. Works for both Groq and Ollama (both stream)."""
    client, model, _ = get_client()
    stream = client.chat.completions.create(
        model=model,
        max_tokens=300,
        stream=True,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# Groq's llama sometimes emits tool calls as text like
# `<function=get_time>` or `<function=remember_fact {"fact": "x"}>` instead of a
# real tool_call. This parses that fallback so tools still fire.
_FUNC_RE = re.compile(r"<function=(\w+)\s*(\{[^}]*\})?\s*>")


def _salvage_failed_call(err: str):
    """Extract the intended tool call from a Groq 'tool_use_failed' error body
    (its 'failed_generation' includes {"name": ..., "arguments": {...}})."""
    m = re.search(r'"name"\s*:\s*"(\w+)"', err)
    if not m or m.group(1) not in TOOLS:
        return None
    args = {}
    a = re.search(r'"arguments"\s*:\s*(\{.*?\})[,}\s]', err.replace("\\n", " "))
    if a:
        try:
            args = json.loads(a.group(1).replace('\\"', '"'))
        except Exception:
            args = {}
    return m.group(1), args


def _parse_text_tool_calls(content: str):
    calls = []
    for name, argstr in _FUNC_RE.findall(content or ""):
        try:
            args = json.loads(argstr) if argstr else {}
        except Exception:
            args = {}
        calls.append((name, args))
    return calls


# Words that suggest a hard/teaching ask worth the bigger free model.
_HARD = re.compile(r"\b(teach|explain|analy[sz]e|review|debug|design|plan|compare|"
                   r"summari[sz]e|why|how does|walk me through|in detail)\b", re.I)


def _pick_model(model: str, label: str, user_text: str) -> str:
    """On Groq, escalate hard/teaching asks to the (also free) 120B."""
    if label == "groq" and (len(user_text) > 220 or _HARD.search(user_text)):
        return GROQ_MODEL_SMART
    return model


def run_turn(user_text: str, system: str = SYSTEM_PROMPT, history: list | None = None) -> str:
    """Tool-enabled turn. `history` = prior [{'role','content'},…] exchanges from
    this session so follow-ups ("and tomorrow?") make sense. The brain may call
    registered tools; we run them, feed results back, and return the spoken reply."""
    client, model, label = get_client()
    model = _pick_model(model, label, user_text)
    if TOOL_SCHEMAS:
        # Lean nudge + explicit ROUTING rules (cutting these once made the model
        # open a browser for "what's the weather" — never again).
        system += (
            " Use your tools for anything they can answer or do — never say you don't know "
            "something a tool provides, and never fabricate data. ROUTING: weather → "
            "get_weather, and pass city ONLY if the user names one (no city = their real "
            "location — never invent a city); time/date → get_time; places near the user → "
            "search_nearby; the user's own projects (job-copilot, inventory-service, etc.) → "
            "list_projects/project_info; coding tasks on those projects ('add X to my "
            "portfolio') → delegate_coding; distance/how-far/travel-time → get_distance "
            "(answer it yourself, "
            "don't tell the user to check a map); opening things → open_app first, "
            "open_website if no app matches; what's on screen → see_screen. Use "
            "web_search/read_page ONLY when no dedicated tool fits — they launch a visible "
            "browser window, so they're a last resort. Gated actions are NOT done until the "
            "user confirms. Answer ONLY what was asked — never recite extra fields a tool "
            "returned (e.g. don't add tomorrow's forecast unless asked). When the user spells "
            "a word ('P-I-N-D'), reconstruct it ('Pind') and pass CLEAN canonical names to "
            "tools — never spelled-out letters or phrases like 'I meant'. If a tool can't find "
            "something, say so plainly and ask the user to correct you. Keep replies short "
            "and speakable."
        )
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    for _ in range(4):  # bound the tool loop
        kwargs = dict(model=model, messages=messages, max_tokens=400)
        if TOOL_SCHEMAS:
            kwargs.update(tools=TOOL_SCHEMAS, tool_choice="auto")
        try:
            msg = client.chat.completions.create(**kwargs).choices[0].message
        except Exception as e:
            # Free-tier rate limit / transient server error: wait briefly, retry once.
            if any(x in str(e) for x in ("429", "rate_limit", "503", "502")):
                import time as _t
                _t.sleep(4)
                try:
                    msg = client.chat.completions.create(**kwargs).choices[0].message
                except Exception:
                    return ("I'm being rate limited at the moment — "
                            "give me a few seconds and ask again.")
                if not msg.tool_calls:
                    return (msg.content or "").strip() or "Done."
                messages.append(msg.model_dump(exclude_none=True))
                for call in msg.tool_calls:
                    try:
                        args = json.loads(call.function.arguments or "{}")
                    except Exception:
                        args = {}
                    args = _sanitize(call.function.name, args, user_text)
                    result = _dispatch(call.function.name, TOOLS.get(call.function.name), args)
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "content": json.dumps(result)})
                continue
            # Groq sometimes 400s a malformed tool call ('tool_use_failed') — and
            # the error body handily contains the INTENDED call. Salvage it: run
            # that tool ourselves and let the loop continue with its result.
            if "tool_use_failed" not in str(e) and "tool call validation" not in str(e):
                raise
            salvaged = _salvage_failed_call(str(e))
            if salvaged:
                name, args = salvaged
                args = _sanitize(name, args, user_text)
                result = _dispatch(name, TOOLS.get(name), args)
                messages.append({"role": "user",
                                 "content": f"[result of {name}]: {json.dumps(result)}"})
                continue
            try:   # nothing to salvage → one no-tools retry for a plain reply
                msg = client.chat.completions.create(
                    model=model, messages=messages, max_tokens=400
                ).choices[0].message
            except Exception:
                return "Sorry — that request tripped me up. Could you rephrase?"
        if not msg.tool_calls:
            # Handle the text-format tool-call fallback (Groq llama quirk).
            text_calls = _parse_text_tool_calls(msg.content or "")
            if not text_calls:
                return (msg.content or "").strip()
            messages.append({"role": "assistant", "content": msg.content})
            for name, args in text_calls:
                args = _sanitize(name, args, user_text)
                result = _dispatch(name, TOOLS.get(name), args)
                messages.append({"role": "user",
                                 "content": f"[result of {name}]: {json.dumps(result)}"})
            continue
        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except Exception:
                args = {}
            args = _sanitize(call.function.name, args, user_text)
            result = _dispatch(call.function.name, TOOLS.get(call.function.name), args)
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result)})
    # Tool loop exhausted — get a real wrap-up instead of a blind "Done."
    try:
        msg = client.chat.completions.create(
            model=model, max_tokens=150,
            messages=messages + [{"role": "user",
                                  "content": "Briefly tell the user the outcome, in one sentence."}])
        return (msg.choices[0].message.content or "Done.").strip()
    except Exception:
        return "Done."
