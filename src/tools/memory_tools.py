"""Memory tools — explicit teaching. "Remember that I go to the gym at 6am"
stores a durable fact that gets injected into every future brain call
(memory.build_context), so Jarvis knows it next time — even offline.

Recall isn't a tool: known facts are always injected as context, so the brain
just answers from them. See docs/phases/phase-2-memory.md and LEARNING.md.
"""
import memory
from brain import tool


@tool({"name": "remember_fact",
       "description": "Store a durable fact or preference about the user for future recall.",
       "parameters": {"type": "object",
           "properties": {
               "fact": {"type": "string", "description": "the fact to remember"},
               "topic": {"type": "string", "description": "e.g. routine, people, prefs"}},
           "required": ["fact"]}})
def remember_fact(fact: str, topic: str = "general"):
    memory.remember_fact(fact, topic=topic, source="user")
    return {"remembered": fact}
