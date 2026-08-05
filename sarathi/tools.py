"""Day 2: Sarathi tools -- turning plain functions into things a model can call.

Concept: a Tool pairs a callable with the JSON schema the provider needs to
advertise it. The `tool` decorator builds that schema from a function's own
signature so the two never drift apart. `core_tools` hands out a workdir-
scoped toolkit -- read, write, edit, shell, list, grep -- where every path
argument is resolved and checked against the workdir's real path before it
touches disk, so a model can't wander outside its sandbox by way of `..` or
a symlink.
"""

import fnmatch
import inspect
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


@dataclass
class Tool:
    name: str
    spec: dict
    run: Callable


def tool(description, **params):
    """Turn a plain function into a Tool, deriving its schema from its
    signature. Parameters with defaults are optional; the rest are required.
    Every parameter is typed as a string in the schema. `params` maps
    argument name -> description text.
    """

    def decorator(fn):
        properties = {}
        required = []
        for name, param in inspect.signature(fn).parameters.items():
            properties[name] = {"type": "string", "description": params.get(name, "")}
            if param.default is inspect.Parameter.empty:
                required.append(name)
        spec = {
            "schema": {
                "name": fn.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        }
        return Tool(name=fn.__name__, spec=spec, run=fn)

    return decorator


def _skip_dirs(dirnames):
    dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]


def _matches(rel, name, pattern):
    """fnmatch against the relative path and the basename. A leading '**/'
    is also tried stripped, since fnmatch's '*' already spans '/' and would
    otherwise never match a top-level file against e.g. the default '**/*'.
    """
    candidates = (pattern, pattern[3:]) if pattern.startswith("**/") else (pattern,)
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in candidates)


def core_tools(workdir):
    """Build the six file/shell tools, all confined to the real path of
    `workdir`.
    """
    root = os.path.realpath(workdir)

    def resolve(path):
        full = os.path.realpath(os.path.join(root, path))
        if full != root and not full.startswith(root + os.sep):
            raise PermissionError(f"{path!r} escapes the working directory")
        return full

    @tool(
        "Read a file's contents, with line numbers.",
        path="Path to the file, relative to the working directory",
    )
    def read_file(path):
        full = resolve(path)
        with open(full, "r") as f:
            lines = f.read().splitlines()
        total = len(lines)
        shown = lines[:4000]
        numbered = "\n".join(f"{i}\t{line}" for i, line in enumerate(shown, 1))
        if total > 4000:
            numbered += f"\n... truncated, {total} lines total"
        return numbered

    @tool(
        "Write content to a file, creating parent directories as needed.",
        path="Path to the file, relative to the working directory",
        content="The full content to write",
    )
    def write_file(path, content):
        full = resolve(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {path}"

    @tool(
        "Replace an exact snippet of text in a file with new text. The "
        "snippet must appear exactly once.",
        path="Path to the file, relative to the working directory",
        old="The exact snippet to replace",
        new="The text to replace it with",
    )
    def edit_file(path, old, new):
        full = resolve(path)
        with open(full, "r") as f:
            content = f.read()
        count = content.count(old)
        if count == 0:
            return "ERROR: snippet not found — read the file and copy it exactly"
        if count > 1:
            return f"ERROR: snippet appears {count} times — include more context to make it unique"
        with open(full, "w") as f:
            f.write(content.replace(old, new, 1))
        return f"Edited {path}"

    @tool(
        "Run a shell command in the working directory.",
        command="The shell command to run",
        timeout="Timeout in seconds",
    )
    def bash(command, timeout="120"):
        seconds = float(timeout)
        # HOME is pinned to the sandbox so `~`/$HOME expansion -- by the
        # shell itself, or by anything the command runs that consults HOME
        # (python's os.path.expanduser, git, npm, ...) -- can't reach the
        # real home directory, even via indirection a static check misses.
        env = dict(os.environ, HOME=root)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=seconds,
            )
        except subprocess.TimeoutExpired:
            return f"ERROR: timed out after {timeout}s"

        output = proc.stdout + proc.stderr
        if not output:
            return f"(exit {proc.returncode}, no output)"
        if len(output) > 12000:
            output = output[:6000] + "\n... [truncated] ...\n" + output[-6000:]
        return output

    @tool(
        "List files under the working directory matching a glob pattern.",
        pattern="Glob pattern, e.g. '**/*.py' (default '**/*')",
    )
    def list_files(pattern="**/*"):
        matches = []
        for dirpath, dirnames, filenames in os.walk(root):
            _skip_dirs(dirnames)
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                if _matches(rel, name, pattern):
                    matches.append(rel)
        matches.sort()
        if len(matches) > 500:
            return "\n".join(matches[:500]) + f"\n... and {len(matches) - 500} more"
        return "\n".join(matches)

    @tool(
        "Search file contents for a regex pattern, across files matching a "
        "glob.",
        regex="The regular expression to search for",
        pattern="Glob pattern to filter which files are searched (default '*')",
    )
    def grep(regex, pattern="*"):
        compiled = re.compile(regex)
        hits = []
        for dirpath, dirnames, filenames in os.walk(root):
            _skip_dirs(dirnames)
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root)
                if not _matches(rel, name, pattern):
                    continue
                try:
                    with open(full, "r", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            if compiled.search(line):
                                hits.append(f"{rel}:{lineno}: {line.rstrip(chr(10))[:200]}")
                                if len(hits) >= 200:
                                    return "\n".join(hits)
                except OSError:
                    continue
        return "\n".join(hits)

    return [read_file, write_file, edit_file, bash, list_files, grep]
