"""Day 1 demo: a hand-written dice-rolling tool, run through the full loop.

Concept: prove the round-trip works end to end -- a user task, an assistant
tool call, a tool result, and a final assistant answer -- with the smallest
possible tool.

Run with: python3 -m demos.day1_dice
"""

import random

from sarathi import provider
from sarathi.loop import run_loop

TASK = "Roll 3 dice and tell me whether the total beats 10."


class RollDice:
    """Rolls `count` six-sided dice and returns the individual results."""

    spec = {
        "schema": {
            "name": "roll_dice",
            "description": "Roll count six-sided dice",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "string", "description": "How many dice"},
                },
                "required": ["count"],
            },
        }
    }

    def run(self, count):
        return [random.randint(1, 6) for _ in range(int(count))]


def on_event(kind, payload):
    """Print each turn of the transcript as it happens."""
    if kind == "assistant":
        if payload["text"]:
            print(f"assistant: {payload['text']}")
        for call in payload["tool_calls"]:
            print(f"assistant -> tool call: {call['name']}({call['args']})")
    elif kind == "tool_end":
        print(f"tool result -> {payload['name']}: {payload['text']}")


def before_tool(call):
    """Always allow; day 1 has no policy layer yet."""
    return None


def main():
    print(f"user: {TASK}")
    messages = [{"role": "user", "text": TASK}]
    tools = {"roll_dice": RollDice()}
    answer = run_loop(
        provider.DEFAULT_MODEL,
        "You are a helpful assistant with access to tools.",
        messages,
        tools,
        on_event,
        before_tool,
    )
    print(f"assistant: {answer}")


if __name__ == "__main__":
    main()
