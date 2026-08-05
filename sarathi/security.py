"""Day 2: Sarathi security -- the policy gate between the model and its tools.

Concept: every tool call passes through check() before it runs. A denied
bash pattern is a floor no policy mode can lift -- it blocks regardless of
mode. Above that floor, reads are always free, and mode decides whether
anything else runs unchecked (yolo), never (read-only), or only with a
human's yes (safe).
"""

import re

READ_TOOLS = {"read_file", "list_files", "grep"}

DENY_PATTERNS = [
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*(\s+\S+)*\s+(/|~|\$HOME)(?:[\s/]|$)",
    r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*(\s+\S+)*\s+(/|~|\$HOME)(?:[\s/]|$)",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"curl\s[^\n|]*\|\s*(sudo\s+)?sh\b",
    r"git\s+push\b[^\n]*--force\b",
    r">\s*/dev/sd[a-z]\d*\b",
]


def _refuse(call, reason):
    """Default approver: nothing gets a yes without one being wired up."""
    return False


class Policy:
    def __init__(self, mode="safe", approver=None):
        self.mode = mode
        self.approver = approver or _refuse

    def check(self, call):
        """Return None to allow `call`, or a reason string to block it."""
        if call["name"] == "bash":
            command = call.get("args", {}).get("command", "")
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
