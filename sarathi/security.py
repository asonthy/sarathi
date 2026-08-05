"""Day 2 (hardened): Sarathi security -- the policy gate between the model
and its tools.

Concept: every tool call passes through check() before it runs. A denied
bash pattern is a floor no policy mode can lift -- it blocks regardless of
mode. Above that floor, reads are always free, and mode decides whether
anything else runs unchecked (yolo), never (read-only), or only with a
human's yes (safe).

Deleting $HOME gets its own check, separate from DENY_PATTERNS: regex on
raw text can't tell "rm -rf ~" (catastrophic) from "rm -rf ~/../sandbox"
(fine) or survive flag reordering ("-fr" vs "-Rf" vs "--recursive --force").
_deletes_home tokenizes each command segment with shlex, resolves whatever
path a delete-capable command targets against the real filesystem, and
blocks only when that resolved path is $HOME itself or falls under it
*outside* the current sandbox -- so routine cleanup inside the project
directory still works even when that directory happens to live under
$HOME. This is still text-level analysis, so it can't see through
sufficiently indirected attacks (a path built at runtime and handed to a
non-shell interpreter, say); sarathi.tools.bash pairs this with a runtime
HOME override as a second, independent layer.
"""

import os
import re
import shlex

READ_TOOLS = {"read_file", "list_files", "grep"}

HOME_DIR = os.path.realpath(os.path.expanduser("~"))

DELETE_COMMANDS = {"rm", "rmdir", "shred", "srm", "unlink"}

DENY_PATTERNS = [
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"curl\s[^\n|]*\|\s*(sudo\s+)?sh\b",
    r"git\s+push\b[^\n]*--force\b",
    r">\s*/dev/sd[a-z]\d*\b",
]

_SEGMENT_SPLIT = re.compile(r"&&|\|\||[;&|\n]")
_HOME_TOKEN = re.compile(r"~|\$\{?HOME\}?")
_DELETE_NAME = re.compile(r"\b(?:rm|rmdir|shred|srm|unlink)\b")


def _segments(command):
    """Best-effort split of a shell command into pipeline segments on ;, &&,
    ||, |, & and newlines. This doesn't account for those characters
    appearing inside quotes -- a gap the runtime HOME override in
    sarathi.tools.bash exists to cover.
    """
    return [s for s in _SEGMENT_SPLIT.split(command) if s.strip()]


def _within(path, root):
    """True if `path` is `root` or lives under it. `root` == "/" contains
    everything.
    """
    if root == os.sep:
        return True
    return path == root or path.startswith(root + os.sep)


def _resolve(path, sandbox):
    path = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(path):
        path = os.path.join(sandbox, path)
    return os.path.realpath(path)


def _targets_home_outside_sandbox(path, sandbox):
    if _within(path, sandbox):
        return False
    return _within(path, HOME_DIR) or _within(HOME_DIR, path)


def _find_roots(tokens):
    """find's search roots: positional args before the first flag."""
    roots = []
    for t in tokens[1:]:
        if t.startswith("-"):
            break
        roots.append(t)
    return roots


def _deletes_home(command, sandbox):
    """True if any segment of `command` resolves a delete to $HOME or a
    path outside `sandbox` that falls under $HOME.
    """
    for segment in _segments(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            # Unbalanced quotes -- can't safely tokenize. Fall back to a
            # conservative text check rather than silently letting it pass.
            if _DELETE_NAME.search(segment) and _HOME_TOKEN.search(segment):
                return True
            continue

        if not tokens:
            continue

        name = os.path.basename(tokens[0])
        if name in DELETE_COMMANDS:
            paths = [t for t in tokens[1:] if not t.startswith("-")]
        elif name == "find" and ("-delete" in tokens or "-exec" in tokens):
            paths = _find_roots(tokens)
        else:
            continue

        for p in paths:
            if _targets_home_outside_sandbox(_resolve(p, sandbox), sandbox):
                return True

    return False


def _refuse(call, reason):
    """Default approver: nothing gets a yes without one being wired up."""
    return False


class Policy:
    def __init__(self, mode="safe", approver=None, workdir=None):
        self.mode = mode
        self.approver = approver or _refuse
        self.sandbox = os.path.realpath(workdir) if workdir else os.path.realpath(os.getcwd())

    def check(self, call):
        """Return None to allow `call`, or a reason string to block it."""
        if call["name"] == "bash":
            command = call.get("args", {}).get("command", "")

            if _deletes_home(command, self.sandbox):
                return f"command would delete $HOME ({HOME_DIR}) or a path under it outside the sandbox"

            for pattern in DENY_PATTERNS:
                if re.search(pattern, command):
                    return f"command matches denied pattern: {pattern}"

        if call["name"] in READ_TOOLS or self.mode == "yolo":
            return None

        if self.mode == "read-only":
            return f"read-only mode: {call['name']} is not permitted"

        reason = f"approve {call['name']}({call.get('args', {})})?"
        if self.approver(call, reason):
            return None
        return f"not approved: {call['name']}"
