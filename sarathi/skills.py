"""Day 3: Sarathi skills -- optional instruction bundles loaded on demand.

Concept: a skill is a directory with a SKILL.md. The agent sees only a
one-line catalog entry by default and pulls in the full text through a tool
only when a task actually calls for it, so the system prompt stays cheap
until a skill earns its place.
"""

import os
import re

SKILLS_DIR = "skills"


def _description(text):
    """Pull the 'description:' line out of a leading '---' front matter
    block, if the file has one.
    """
    if not text.startswith("---"):
        return ""
    end = text.find("---", 3)
    if end == -1:
        return ""
    match = re.search(r"^description:\s*(.+)$", text[3:end], re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def catalog(workdir):
    root = os.path.join(os.path.realpath(workdir), SKILLS_DIR)
    found = {}
    if not os.path.isdir(root):
        return found
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name, "SKILL.md")
        if not os.path.isfile(path):
            continue
        with open(path, "r") as f:
            text = f.read()
        found[name] = {"description": _description(text), "path": path}
    return found


def catalog_prompt(workdir):
    skills = catalog(workdir)
    if not skills:
        return ""
    lines = ["Skills available (load one with the use_skill tool when relevant):"]
    lines += [f"- {name}: {info['description']}" for name, info in skills.items()]
    return "\n".join(lines)


def read_skill(workdir, name):
    skills = catalog(workdir)
    if name not in skills:
        available = ", ".join(sorted(skills)) or "none"
        return f"ERROR: no skill named {name}. Available: {available}"
    with open(skills[name]["path"], "r") as f:
        return f.read()
