"""Day 3: Sarathi memory -- durable notes that outlive a single run.

Concept: SARATHI.md is a project's standing memory. It gets folded into the
system prompt of every conversation over that directory, so a fresh session
already knows what a prior one learned.
"""

import os
import platform

MEMORY_FILE = "SARATHI.md"

BASE_SYSTEM_PROMPT = (
    "You are Sarathi, a small sharp coding agent working inside one "
    "directory with the tools provided. Act, don't narrate. Inspect before "
    "assuming. Prefer edit_file for small changes. Verify after building by "
    "running or re-reading. Never repeat a failing call unchanged. When "
    "complete, reply with a short summary and stop calling tools."
)


def build_system_prompt(workdir, extra=""):
    real = os.path.realpath(workdir)
    sections = [
        BASE_SYSTEM_PROMPT,
        f"Platform: {platform.system()}. Working directory: {real}",
    ]

    memory_path = os.path.join(real, MEMORY_FILE)
    if os.path.exists(memory_path):
        with open(memory_path, "r") as f:
            contents = f.read()
        sections.append(f"Project memory ({MEMORY_FILE}):\n{contents}")

    if extra:
        sections.append(extra)

    return "\n\n".join(sections)


def remember(workdir, note):
    path = os.path.join(os.path.realpath(workdir), MEMORY_FILE)
    with open(path, "a") as f:
        f.write(f"- {note}\n")
    return f"Remembered in {MEMORY_FILE}"
