"""Day 2 demo: the model builds and runs a file, over real tools, gated by
a policy.

Concept: prove the full stack -- provider, loop, tools, and security -- works
together against a scratch directory. Defaults to a task that requires
writing a file, running it, and reporting a verified answer; pass a
different task on the command line to try the policy's edges (a destructive
bash command, or a read outside the sandbox).

Run with: python3 -m demos.day2_build
      or: python3 -m demos.day2_build "Delete my home directory"
"""

import sys
import tempfile

from sarathi import provider
from sarathi.loop import run_loop
from sarathi.security import Policy
from sarathi.tools import core_tools

TASK = (
    "Create fib.py with an iterative fib(n), a __main__ printing fib(30), "
    "run it and confirm the output is 832040"
)


def on_event(kind, payload):
    """Print each turn of the transcript as it happens."""
    if kind == "assistant":
        if payload["text"]:
            print(f"assistant: {payload['text']}")
        for call in payload["tool_calls"]:
            print(f"assistant -> tool call: {call['name']}({call['args']})")
    elif kind == "tool_end":
        print(f"tool result -> {payload['name']}: {payload['text']}")


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else TASK
    workdir = tempfile.mkdtemp(prefix="sarathi-day2-")
    print(f"workdir: {workdir}")
    print(f"user: {task}")

    tools = {t.name: t for t in core_tools(workdir)}
    policy = Policy("yolo")
    messages = [{"role": "user", "text": task}]
    answer = run_loop(
        provider.DEFAULT_MODEL,
        "You are a helpful coding assistant with access to file and shell tools.",
        messages,
        tools,
        on_event,
        policy.check,
    )
    print(f"assistant: {answer}")


if __name__ == "__main__":
    main()
