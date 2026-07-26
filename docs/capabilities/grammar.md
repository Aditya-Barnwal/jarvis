# Capability: Grammar & writing help

> ⚠️ **Historical blueprint.** The implemented system differs in places (brain models, TTS package, defaults). For what's actually built, see [../build/](../build/).

**What you want:** "Fix my grammar", "make this sound better", "is this message okay to send?"

**Reality:** ✅ fully built-in, zero extra infrastructure. The brain (Groq or Ollama) does this natively and well.

---

## How it works

This isn't a separate tool so much as a mode of the brain. Any time you hand Jarvis text — dictated, from the clipboard, or a draft message — the brain can return a corrected/improved version and explain what changed.

```python
# src/tools/grammar.py
@tool({
    "name": "fix_writing",
    "description": "Correct grammar and improve clarity of a piece of text. Returns corrected text and a short note on changes.",
    "parameters": {"type": "object",
        "properties": {
            "text": {"type": "string"},
            "tone": {"type": "string", "description": "e.g. casual, formal, friendly"}},
        "required": ["text"]},
})
def fix_writing(text: str, tone: str = "keep original"):
    # thin wrapper — the actual correction is done by the brain when it calls this
    # (or Jarvis just corrects inline without a tool call at all)
    ...
```

In practice you often don't even need a tool call — Jarvis corrects inline as part of composing a message. The tool is useful when you want to explicitly check a block of text from the clipboard.

## Use patterns

- **In messaging** — every WhatsApp/SMS/email draft is silently grammar-checked before hand-off. See [whatsapp.md](whatsapp.md).
- **Clipboard check** — "Jarvis, check what I just wrote" → reads clipboard via `pbpaste`, returns a corrected version, optionally copies it back.
- **Tone shift** — "make this more formal / friendlier / shorter" — same mechanism, different instruction.
- **Language help** — spot awkward phrasing, suggest cleaner alternatives, explain a correction if you ask why.

## Example

```
You (clipboard): "i has went to the store and buyed milk"
Jarvis: "Corrected: 'I went to the store and bought milk.'
         Fixed the verb tenses — 'has went' → 'went', 'buyed' → 'bought'.
         Copied it back to your clipboard."
```

## Why this one is easy

Grammar correction is squarely in a language model's wheelhouse — no APIs, no scraping, no permissions, no ban risk. It's the cleanest capability in the project. It just rides on the brain you already have.
