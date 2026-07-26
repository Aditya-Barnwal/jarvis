"""Tool-call routing reliability test — measure only, change nothing.

Reuses the REAL brain + dispatch path (brain.run_turn) with the SAME system
prompt talk.py builds and the SAME registered tool schemas. To avoid side
effects, each registered tool callable is swapped for a no-op *recorder* that
logs (name, args) — so we measure which tool the model chose without mutating
memory or voice state. The model, prompt, and schemas are untouched.

Runs every case N times through each available backend (Groq 70B if a key
exists; Ollama qwen2.5:7b; Ollama llama3.2:3b for reference) and reports
routing accuracy plus the two failure modes that matter for hands-free:
narration-instead-of-tool, and false-positive-tool-on-conversation.

    python tests/routing_test.py            # 3 trials/case
    python tests/routing_test.py 5          # 5 trials/case
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from openai import OpenAI

import brain
import config
import talk               # for build_system (same prompt as the live loop)
from personas import JARVIS

# ---- cases (expected routing) --------------------------------------------
CASES = [
    {"id": 1, "text": "Remember that my sister's name is Anjali.",
     "expect": {"tool": "remember_fact"}},
    {"id": 2, "text": "Open Spotify and turn the volume down to 30.",
     "expect": {"skip": "open_app/control_volume not registered (Phase 3)"}},
    {"id": 3, "text": "What's my sister's name?",
     "expect": {"none": True, "note": "recall is context-injection, not a tool"}},
    {"id": 4, "text": "Do you think the volume's a bit too loud right now?",
     "expect": {"none": True, "note": "look-alike trap — conversation"}},
    {"id": 5, "text": "From now on your name is Vega.",
     "expect": {"tool": "rename_self", "arg": ("name", "vega")}},
    {"id": 6, "text": "Talk to me more softly.",
     "expect": {"tool": "set_emotion", "arg": ("emotion", "soft")}},
    {"id": 7, "text": "Go a bit deeper.",
     "expect": {"tool": "set_pitch", "argcheck": "negative"}},
    {"id": 8, "text": "How was my day?",
     "expect": {"none": True, "note": "conversation"}},
]

# ---- swap tools for no-op recorders (no side effects) ---------------------
_recorded: list[tuple[str, dict]] = []


def _install_recorders():
    for name in list(brain.TOOLS):
        def make(n):
            def rec(**kwargs):
                _recorded.append((n, kwargs))
                return {"ok": True}
            return rec
        brain.TOOLS[name] = make(name)


# Same system prompt the live loop uses (persona + emotion + memory context).
SYSTEM = talk.build_system(JARVIS)


def _force_backend(client, model, label):
    brain.get_client = lambda: (client, model, label)


def _run_once(text):
    _recorded.clear()
    try:
        reply = brain.run_turn(text, SYSTEM)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "calls": [], "reply": ""}
    return {"error": None, "calls": list(_recorded), "reply": reply}


def _classify(case, calls, reply):
    """-> one of PASS, ARGWARN, NARRATED, NOTOOL, WRONGTOOL, FALSEPOS, SKIP.
    NARRATED = said something but called no tool; NOTOOL = silent (empty)."""
    exp = case["expect"]
    if "skip" in exp:
        return "SKIP"
    if exp.get("none"):
        return "PASS" if not calls else "FALSEPOS"
    tool = exp["tool"]
    names = [c[0] for c in calls]
    if tool not in names:
        if calls:
            return "WRONGTOOL"
        return "NARRATED" if reply.strip() else "NOTOOL"
    args = next(c[1] for c in calls if c[0] == tool)
    if "arg" in exp:
        k, v = exp["arg"]
        return "PASS" if str(args.get(k, "")).strip().lower() == v else "ARGWARN"
    if exp.get("argcheck") == "negative":
        try:
            return "PASS" if float(args.get("semitones", 0)) < 0 else "ARGWARN"
        except (TypeError, ValueError):
            return "ARGWARN"
    return "PASS"


ROUTE_OK = {"PASS", "ARGWARN"}   # tool chosen correctly (arg may be off)


def run_backend(label, client, model, trials):
    _force_backend(client, model, label)
    print(f"\n{'='*72}\nBACKEND: {label}  ·  model={model}  ·  {trials} trials/case\n{'='*72}")
    rows, narrated, notool, falsepos = [], [], [], []
    testable_pass = testable_total = 0
    for case in CASES:
        results = []
        for _ in range(trials):
            out = _run_once(case["text"])
            if out["error"]:
                results.append(f"ERR({out['error'][:30]})")
                continue
            status = _classify(case, out["calls"], out["reply"])
            results.append(status)
            if status == "NARRATED":
                narrated.append((case["id"], case["text"], out["reply"][:70]))
            if status == "NOTOOL":
                notool.append((case["id"], case["text"]))
            if status == "FALSEPOS":
                falsepos.append((case["id"], case["text"], out["calls"]))
        skipped = case["expect"].get("skip")
        if not skipped:
            ok = sum(1 for r in results if r in ROUTE_OK)
            testable_pass += ok
            testable_total += len(results)
            score = f"{ok}/{trials}"
        else:
            score = "SKIP"
        rows.append((case, results, score))
        exp_str = ("SKIP: " + skipped) if skipped else (
            "no tool" if case["expect"].get("none") else case["expect"]["tool"])
        print(f"  [{case['id']}] {case['text'][:46]:46}  exp={exp_str[:26]:26}  "
              f"{score:6}  {results}")
    rate = 100 * testable_pass / testable_total if testable_total else 0
    print(f"\n  >>> {label} routing accuracy: {testable_pass}/{testable_total} "
          f"= {rate:.0f}%  (testable cases only; case 2 skipped)")
    if narrated:
        print("  ⚠️  NARRATED instead of calling tool (said it, no tool_call):")
        for cid, t, r in narrated:
            print(f"       [{cid}] {t!r} -> said {r!r}")
    if notool:
        print("  ⚠️  SILENT no-op (no tool_call AND no reply):")
        for cid, t in notool:
            print(f"       [{cid}] {t!r}")
    if falsepos:
        print("  ⚠️  FALSE POSITIVE (tool on conversation):")
        for cid, t, c in falsepos:
            print(f"       [{cid}] {t!r} -> {c}")
    return (label, model, rate, testable_pass, testable_total,
            len(narrated), len(notool), len(falsepos))


def main():
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    _install_recorders()
    print(f"Registered tools: {sorted(brain.TOOLS)}")
    print(f"System prompt (first 120 chars): {SYSTEM[:120]!r}...")

    summary = []

    # Groq online brain — runs the instant a GROQ_API_KEY exists in env/.env,
    # otherwise skips cleanly (not stubbed). Add a key and re-run for numbers.
    if config.has_groq_key():
        groq = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
        summary.append(run_backend("Groq", groq, "llama-3.3-70b-versatile", trials))
    else:
        print("\n[Groq — no key — skipped]  (set GROQ_API_KEY in .env to test the "
              "online 70B brain; harness runs it automatically once present)")

    ollama = OpenAI(api_key="ollama", base_url=config.OLLAMA_BASE_URL)
    # Primary offline brain (the real fallback we care about):
    summary.append(run_backend("Ollama", ollama, "qwen2.5:7b", trials))
    # Reference: the model Milestone 2 actually ran on — if it routes worse than
    # 7b, that partly explains any flakiness seen in M2.
    summary.append(run_backend("Ollama (what M2 used)", ollama, "llama3.2:3b", trials))

    print(f"\n{'#'*72}\nSUMMARY\n{'#'*72}")
    print(f"{'backend':12} {'model':26} {'routing':>9}  {'narrated':>8}  {'silent':>6}  {'false+':>6}")
    for label, model, rate, p, t, nar, noo, fp in summary:
        print(f"{label:12} {model:26} {p}/{t}={rate:>3.0f}%  {nar:>8}  {noo:>6}  {fp:>6}")


if __name__ == "__main__":
    main()
