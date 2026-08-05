"""Day 3 demo: context compaction, durable memory, and skills, wired into
the loop.

Concept: prove all three pieces work together over a scratch directory -- a
long task that forces mid-run compaction, a memory note that survives into a
fresh conversation over the same directory, and a skill that reshapes the
agent's voice with zero code changes.

Run with: python3 -m demos.day3_context "task"
      or: python3 -m demos.day3_context --workdir /path --budget 1500 "task"
"""

import argparse
import os
import tempfile

from sarathi import context, memory, provider, skills
from sarathi.loop import run_loop
from sarathi.security import Policy
from sarathi.tools import core_tools, tool

DEFAULT_TASK = (
    "Create five files one.txt through five.txt, each with 20 lines of the "
    "word ping, one write_file at a time with a read back after each; then "
    "MANIFEST.md listing each file and its line count verified with wc -l"
)


def build_tools(workdir):
    """The six sandboxed file/shell tools, plus memory and skill access."""
    tools = {t.name: t for t in core_tools(workdir)}

    @tool(
        "Save a durable note to project memory (SARATHI.md) for future "
        "sessions over this directory.",
        note="The fact or note to remember",
    )
    def remember(note):
        return memory.remember(workdir, note)

    @tool(
        "Load a skill's full instructions by name, from the skills catalog.",
        name="The skill name",
    )
    def use_skill(name):
        return skills.read_skill(workdir, name)

    tools[remember.name] = remember
    tools[use_skill.name] = use_skill
    return tools


def on_event(kind, payload):
    """Print each turn of the transcript as it happens."""
    if kind == "assistant":
        if payload["text"]:
            print(f"assistant: {payload['text']}")
        for call in payload["tool_calls"]:
            print(f"assistant -> tool call: {call['name']}({call['args']})")
    elif kind == "tool_end":
        print(f"tool result -> {payload['name']}: {payload['text']}")


def make_before_turn(model, budget_tokens):
    """Wrap context.compact so a demo run can see when compaction fires."""

    def before_turn(messages):
        before_count = len(messages)
        before_tokens = context.estimate_tokens(messages)
        compacted = context.compact(model, messages, budget_tokens)
        if len(compacted) != before_count:
            after_tokens = context.estimate_tokens(compacted)
            print(
                f"[context] compacted {before_count} messages (~{before_tokens:.0f} tok) "
                f"-> {len(compacted)} messages (~{after_tokens:.0f} tok)"
            )
        return compacted

    return before_turn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", nargs="?", default=DEFAULT_TASK)
    parser.add_argument("--workdir", default=None)
    parser.add_argument("--budget", type=int, default=8000)
    args = parser.parse_args()

    workdir = args.workdir or tempfile.mkdtemp(prefix="sarathi-day3-")
    os.makedirs(workdir, exist_ok=True)
    print(f"workdir: {workdir}")
    print(f"user: {args.task}")

    tools = build_tools(workdir)
    policy = Policy("yolo", workdir=workdir)
    system = memory.build_system_prompt(workdir, extra=skills.catalog_prompt(workdir))
    messages = [{"role": "user", "text": args.task}]

    answer = run_loop(
        provider.DEFAULT_MODEL,
        system,
        messages,
        tools,
        on_event,
        policy.check,
        before_turn=make_before_turn(provider.DEFAULT_MODEL, args.budget),
    )
    print(f"assistant: {answer}")


if __name__ == "__main__":
    main()
