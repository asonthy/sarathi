"""Day 3: Sarathi context -- keeping a long-running transcript inside budget.

Concept: before each turn, check whether the transcript still fits. If it
doesn't, ask the model to compress everything except the last few turns into
one dense summary, then splice that summary back in as a single user
message. A tool result stranded at the front of the kept slice is meaningless
without the call that produced it, so it gets dropped rather than confuse
the model on the next turn.
"""

from . import provider

CHARS_PER_TOKEN = 4
KEEP_RECENT = 6

_SUMMARY_SYSTEM = (
    "You compress agent transcripts. Preserve: the original task, every file "
    "created or edited and its purpose, key decisions, unresolved errors, "
    "and what remains to be done. Be dense and factual."
)


def estimate_tokens(messages):
    return sum(len(str(m)) for m in messages) / CHARS_PER_TOKEN


def _render(messages):
    lines = []
    for msg in messages:
        role = msg["role"]
        text = (msg.get("text") or "")[:400]
        if role == "tool":
            lines.append(f"tool ({msg['name']}): {text}")
        elif role == "assistant":
            line = f"assistant: {text}" if text else "assistant:"
            calls = msg.get("tool_calls") or []
            if calls:
                line += f" [called: {', '.join(c['name'] for c in calls)}]"
            lines.append(line)
        else:
            lines.append(f"{role}: {text}")
    return "\n".join(lines)


def compact(model, messages, budget_tokens):
    """Return `messages` unchanged if they fit; otherwise summarize
    everything but the last KEEP_RECENT messages into one user message.
    """
    if estimate_tokens(messages) <= budget_tokens or len(messages) <= KEEP_RECENT + 1:
        return messages

    old, recent = messages[:-KEEP_RECENT], messages[-KEEP_RECENT:]
    while recent and recent[0]["role"] == "tool":
        recent = recent[1:]

    reply = provider.complete(
        model,
        _SUMMARY_SYSTEM,
        [{"role": "user", "text": _render(old)}],
        [],
    )
    summary_msg = {
        "role": "user",
        "text": f"[Conversation so far, compacted]\n{reply['text']}",
    }
    return [summary_msg] + recent
