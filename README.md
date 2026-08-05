# Sarathi

A small, sharp coding agent harness — built from scratch, one layer at a
time, to make every piece of an agent loop legible: the turn-taking engine,
the tool sandbox, the security policy, context compaction, durable memory,
and on-demand skills.

No framework, no hidden magic. Sarathi talks to Gemini over raw HTTP and
implements everything else — tool dispatch, retries, path jailing, deny
rules, transcript summarization — in plain, readable Python with zero
third-party dependencies.

> सारथी (*sārathi*) — Sanskrit for "charioteer." Krishna's role for Arjuna
> in the Bhagavad Gita: not the one fighting the battle, but the one holding
> the reins.

## Why

Most agent frameworks bury the interesting parts — the turn loop, the tool
schema, the sandbox boundary — under abstraction. Sarathi does the opposite:
every file is short enough to read in one sitting, and every design
decision is explained in the module's own docstring, not in a separate doc
that drifts out of sync.

## Architecture

```
                     ┌───────────────────────┐
   user task ──────▶ │        loop.py         │ ◀────── on_event (transcript)
                     │  run_loop(): alternate  │
                     │  model turns and tool   │
                     │  turns until the model  │
                     │  stops calling tools    │
                     └──────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
      ┌───────────────┐ ┌───────────────┐ ┌────────────────┐
      │  provider.py   │ │  security.py  │ │    tools.py     │
      │  Gemini wire    │ │  Policy.check  │ │  read/write/edit│
      │  format, retry, │ │  gates every   │ │  /bash/list/grep│
      │  backoff        │ │  tool call     │ │  path-jailed    │
      └───────────────┘ └───────────────┘ └────────────────┘

      before each turn, before_turn hooks in:
      ┌───────────────┐ ┌───────────────┐ ┌────────────────┐
      │  context.py    │ │  memory.py     │ │   skills.py     │
      │  compact long   │ │  SARATHI.md —  │ │  load a SKILL.md│
      │  transcripts    │ │  durable notes │ │  on demand      │
      └───────────────┘ └───────────────┘ └────────────────┘
```

`loop.py` never imports `tools.py` or `security.py` directly — it takes
`tools`, `before_tool`, and `before_turn` as plain arguments. Every other
module is an interchangeable plug-in built by whoever assembles the demo.

## Quickstart

Requires Python 3.9+ and a Gemini API key. No dependencies to install — the
whole harness is standard library.

```bash
git clone git@github.com:asonthy/sarathi.git
cd sarathi
export SARATHI_API_KEY=your-key-here   # or GOOGLE_API_KEY

python3 -m demos.day1_dice                          # loop + provider, one tool
python3 -m demos.day2_build                          # + sandboxed tools + policy
python3 -m demos.day3_context "your task here"       # + context, memory, skills
```

Each demo prints the transcript live — every assistant turn, every tool
call, every result — so you can watch the loop reason and act step by step.

## Core pieces

| Module | What it owns |
|---|---|
| [`provider.py`](sarathi/provider.py) | The only file that speaks Gemini's wire format. Translates a model-agnostic `{"role", "text", ...}` message shape to/from `generateContent`, retries transient failures with exponential backoff, and echoes back the `thoughtSignature` Gemini 3 needs to keep hidden reasoning state coherent. |
| [`loop.py`](sarathi/loop.py) | The turn-taking engine: alternates model turns and tool turns until the model stops calling tools or `max_turns` is hit. A tool that raises never takes down the loop — its failure becomes a tool result the model can react to. |
| [`tools.py`](sarathi/tools.py) | The `@tool` decorator turns a plain function into a callable with a JSON schema derived from its own signature, so the two can't drift apart. `core_tools(workdir)` hands out six tools — `read_file`, `write_file`, `edit_file`, `bash`, `list_files`, `grep` — every path resolved and checked against the workdir's real path before it touches disk. |
| [`security.py`](sarathi/security.py) | `Policy.check()` gates every tool call. A denied `bash` pattern is a floor no mode can lift. Above that, reads are always free; `mode` decides whether anything else runs unchecked (`yolo`), never (`read-only`), or only with a human's yes (`safe`). Home-directory deletion gets its own tokenized, path-resolved check — not just regex — so it survives flag reordering and indirection that a text pattern would miss. |
| [`context.py`](sarathi/context.py) | Before each turn, checks whether the transcript still fits a token budget. If not, summarizes everything but the last few turns into one dense message via the model itself, dropping any orphaned tool result left at the seam. |
| [`memory.py`](sarathi/memory.py) | `SARATHI.md` is a project's standing memory, folded into the system prompt of every conversation over that directory — so a fresh session already knows what a prior one learned. |
| [`skills.py`](sarathi/skills.py) | A skill is a directory with a `SKILL.md`. The agent sees a one-line catalog entry by default and pulls in the full instructions through a tool only when a task calls for it, keeping the system prompt cheap until a skill earns its place. |

## Security model

Every tool call passes through `Policy.check()` before it runs:

1. **Deny patterns are absolute.** `sudo`, `mkfs`, `dd if=`, `curl | sh`,
   `git push --force`, and raw writes to block devices are blocked in every
   mode.
2. **Home-directory deletion is checked structurally, not textually.**
   `_deletes_home` tokenizes each shell segment, resolves whatever path a
   delete-capable command targets against the real filesystem, and blocks
   only when that path is `$HOME` or falls outside the sandbox under it —
   so routine cleanup inside the project directory still works, even when
   that directory happens to live under `$HOME`. `tools.bash` pairs this
   with a runtime `HOME` override pinned to the sandbox as a second,
   independent layer.
3. **Reads are always free**: `read_file`, `list_files`, `grep` never need
   approval.
4. **Everything else depends on mode**: `yolo` runs it, `read-only` blocks
   it, `safe` asks an `approver` callback for a yes.

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
  knows Gemini's wire format. `loop.py` doesn't know what a tool is beyond
  its `run`/`spec` shape. Each module docstring states the concept it
  embodies and the constraint it's built to satisfy.

## Status

Built incrementally, day by day, each day's code committed once its demo
runs end to end. Currently Gemini-only — the neutral message shape in
`provider.py` is designed to make a second backend a matter of adding a
sibling module, not restructuring the loop.
