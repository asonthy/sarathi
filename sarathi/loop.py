"""Day 1: Sarathi loop -- the turn-taking engine that drives a model through
tool calls until it lands on a final answer.

Concept: alternate model turns and tool turns, feeding each tool's result
back as a message, until the model replies with no tool calls left to make.

Design rule this file embodies: a tool that raises never takes down the
loop -- its failure becomes a tool result the model reads and can react to,
just like any other outcome.
"""

from . import provider


def run_loop(model, system, messages, tools, on_event, before_tool,
             max_turns=80, before_turn=None):
    """Drive turns against `tools` (name -> Tool) until the model stops
    calling tools, or `max_turns` is exhausted. Returns the final text.
    """
    specs = [t.spec for t in tools.values()]

    for _ in range(max_turns):
        if before_turn is not None:
            messages = before_turn(messages)

        reply = provider.complete(model, system, messages, specs)
        assistant_msg = {
            "role": "assistant",
            "text": reply["text"],
            "tool_calls": reply["tool_calls"],
        }
        messages.append(assistant_msg)
        on_event("assistant", assistant_msg)

        if not reply["tool_calls"]:
            return reply["text"]

        for call in reply["tool_calls"]:
            on_event("tool_start", call)
            result = _run_tool(tools, before_tool, call)
            tool_msg = {"role": "tool", "name": call["name"], "text": str(result)}
            messages.append(tool_msg)
            on_event("tool_end", tool_msg)

    messages.append({"role": "user", "text": "Turn limit reached; wrap up now."})
    reply = provider.complete(model, system, messages, [])
    messages.append({"role": "assistant", "text": reply["text"], "tool_calls": []})
    return reply["text"]


def _run_tool(tools, before_tool, call):
    """Gate, resolve, and execute one tool call, trapping any failure."""
    reason = before_tool(call)
    if reason is not None:
        return f"BLOCKED: {reason}"

    tool = tools.get(call["name"])
    if tool is None:
        return f"ERROR: unknown tool {call['name']}"

    try:
        return tool.run(**call["args"])
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
