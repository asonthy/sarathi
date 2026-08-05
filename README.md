# Sarathi

*The smallest agent harness that still has a floor under it.*

706 lines, seven files, zero dependencies. A turn-taking loop, sandboxed
tools, a security policy, context compaction, durable memory, and on-demand
skills — built one day at a time, each day committed once its demo runs
end to end. What the agent is *good at* lives outside the code, in
`SARATHI.md` and the skills you drop in `skills/`.

> सारथी (*sārathi*) — Sanskrit for "charioteer." Krishna's role for Arjuna
> in the Bhagavad Gita: not the one fighting the battle, but the one
> holding the reins.

`706` lines · `7` files · `0` dependencies · `3` of a planned `5` days built

---

## The loop

Every coding agent is built around the same eleven lines. Everything else —
tools, policy, memory, context — is scaffolding bolted onto this.

```python
# loop.py, the idea unabridged
for _ in range(max_turns):
    reply = provider.complete(model, system, messages, specs)
    messages.append(reply)
    if not reply["tool_calls"]:
        return reply["text"]
    for call in reply["tool_calls"]:
        result = _run_tool(tools, before_tool, call)
        messages.append({"role": "tool", "name": call["name"], "text": result})
```

**Think.** The model reads the conversation and decides: answer, or act.
**Act.** Six sandboxed tools — read, write, edit, bash, list, grep — are
enough to build real software.
**Observe.** Results, errors included, go back into the conversation. A
tool that raises never takes the loop down with it — its failure becomes
something the model reads and reacts to, same as any other outcome.

## Why small

Most of what ships as an "agent harness" is business around an agent —
chat UI, billing, vendor auth. Sarathi is only the agent. Capability isn't
supposed to live in more code: it lives in `SARATHI.md` (durable,
project-specific memory folded into every system prompt) and in
`skills/*/SKILL.md` (instruction bundles the agent loads by name, on
demand, so the system prompt stays cheap until a skill actually earns its
place). Add a skill file and the agent gets better at something — no code
change required.

## Anatomy

Readable in one sitting, one idea per file.

| File | Lines | Idea |
|---|---:|---|
| [`provider.py`](sarathi/provider.py) | 112 | One narrow doorway to Gemini's wire format — retries, backoff, thought-signature echo. Swap models by rewriting this one file. |
| [`loop.py`](sarathi/loop.py) | 64 | The agentic loop itself. Everything else is scaffolding around it. |
| [`tools.py`](sarathi/tools.py) | 208 | Six sandboxed tools, plus a `@tool` decorator that derives a JSON schema straight from a function's own signature. |
| [`security.py`](sarathi/security.py) | 153 | Deny rules, permission modes (`yolo` / `safe` / `read-only`), and a structural (not regex-only) check that a delete can't reach `$HOME`. |
| [`context.py`](sarathi/context.py) | 66 | Token budget and compaction — long tasks survive a finite context window. |
| [`memory.py`](sarathi/memory.py) | 45 | `SARATHI.md` — one file convention *is* the whole memory system. |
| [`skills.py`](sarathi/skills.py) | 58 | Drop a `SKILL.md` in a folder; the agent gains a capability on demand. |

`session.py`, `subagent.py`, and `fleet.py` — durable resumable sessions,
sub-agent delegation, and multi-agent orchestration — are days 4 and 5,
not yet built here.

## The build log

Each day added one layer, committed once its demo ran end to end. The
prompts each day's code was written from are in [`prompts/`](prompts/).

| Day | What it added | Demo |
|---|---|---|
| 1 | The loop and the Gemini provider — a model that converses and calls its first tool. | [`demos/day1_dice.py`](demos/day1_dice.py) |
| 2 | Sandboxed tools and the security policy — builds and runs real code, gated, in a jail. | [`demos/day2_build.py`](demos/day2_build.py) |
| 3 | Context compaction, durable memory, and skills — survives long tasks, remembers across sessions, learns from markdown. | [`demos/day3_context.py`](demos/day3_context.py) |
| 4 | *Not yet built* — durable sessions, crash recovery, sub-agents. | — |
| 5 | *Not yet built* — fleet orchestration, a real CLI. | — |

A later hardening pass ([`b9cdba6`](../../commit/b9cdba6)) tightened the
day-2 `$HOME`-deletion check from a regex guess to a tokenized,
path-resolved one, backed by a runtime `HOME` override as a second,
independent layer.

## Security model

Every tool call passes through `Policy.check()` before it runs:

1. **Deny patterns are a floor, not a mode.** `sudo`, `mkfs`, `dd if=`,
   `curl | sh`, `git push --force`, and raw writes to block devices are
   blocked no matter what mode you're in.
2. **`$HOME` deletion is checked structurally, not textually.**
   `_deletes_home` tokenizes each shell segment with `shlex`, resolves
   whatever path a delete-capable command targets against the real
   filesystem, and blocks only when that path is `$HOME` — or falls
   outside the sandbox under it — so routine cleanup inside the project
   directory still works even when that directory happens to live under
   `$HOME`.
3. **Reads are always free.** `read_file`, `list_files`, `grep` never need
   approval.
4. **Everything else depends on mode:** `yolo` runs it, `read-only` blocks
   it, `safe` asks an `approver` callback for a yes.

## Quickstart

Python 3.9+ and a Gemini API key. Nothing to `pip install` — the whole
harness is standard library.

```bash
git clone git@github.com:asonthy/sarathi.git
cd sarathi
export SARATHI_API_KEY=your-key-here   # or GOOGLE_API_KEY

python3 -m demos.day1_dice                          # loop + provider, one tool
python3 -m demos.day2_build                          # + sandboxed tools + policy
python3 -m demos.day3_context "your task here"       # + context, memory, skills
```

Each demo prints the transcript live — every assistant turn, every tool
call, every result — so you can watch the loop think and act step by
step.

## Project layout

```
sarathi/
├── sarathi/
│   ├── provider.py    # Gemini client
│   ├── loop.py         # turn-taking engine
│   ├── tools.py         # @tool decorator + sandboxed core tools
│   ├── security.py       # Policy: deny rules + mode gating
│   ├── context.py         # transcript compaction
│   ├── memory.py           # SARATHI.md durable notes
│   └── skills.py             # on-demand skill loading
├── demos/
│   ├── day1_dice.py    # loop + provider, one hand-written tool
│   ├── day2_build.py    # + sandboxed tools + security policy
│   └── day3_context.py    # + context compaction, memory, skills
└── prompts/            # the build prompts each day's code was written from
```

## Design principles

- **A tool that raises never takes down the loop.** Its failure is caught
  and fed back as a tool result the model can read and react to.
- **A denied pattern is a floor, not a mode.** No policy mode lifts a
  blocked `bash` pattern above it.
- **Sandbox by real path, not by string prefix.** Every file tool resolves
  through `os.path.realpath` and checks the result, so `..` and symlinks
  can't walk a call outside the working directory.
- **The system prompt stays cheap until it's earned.** Skills are a
  one-line catalog by default; memory is only loaded if `SARATHI.md`
  exists; context is only compacted once it actually overflows budget.
- **One file, one responsibility.** `provider.py` is the only file that
  knows Gemini's wire format; `loop.py` doesn't know what a tool is beyond
  its `run`/`spec` shape.

---

*Sarathi — distilled from the same idea as Odysseus, built independently, one day at a time.*
