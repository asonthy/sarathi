"""Day 1: Sarathi provider -- the only file that speaks Gemini's wire format.

Concept: translate a small, model-agnostic message shape ({"role", "text",
...}) into Gemini's `generateContent` request/response shape, so the rest of
the harness never has to think about API quirks. Every network call retries
with exponential backoff on rate limits, transient 5xxs, and dropped
connections; tool-call round-trips echo back the thought signature verbatim,
which Gemini 3 requires to keep its hidden reasoning state coherent.
"""

import json
import os
import time
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.1-pro-preview"


def api_key():
    """Return the API key from SARATHI_API_KEY, falling back to GOOGLE_API_KEY."""
    key = os.environ.get("SARATHI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("No API key found: set SARATHI_API_KEY or GOOGLE_API_KEY.")
    return key


def _to_wire(messages):
    """Map neutral messages to Gemini `contents`, one entry per turn."""
    contents = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": msg["text"]}]})
        elif role == "assistant":
            parts = []
            if msg["text"]:
                parts.append({"text": msg["text"]})
            for call in msg["tool_calls"]:
                part = {"functionCall": {"name": call["name"], "args": call["args"]}}
                if call.get("signature"):
                    # Gemini 3 requires this echo to keep reasoning state intact.
                    part["thoughtSignature"] = call["signature"]
                parts.append(part)
            contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            response = {"name": msg["name"], "response": {"result": msg["text"]}}
            contents.append({"role": "user", "parts": [{"functionResponse": response}]})
    return contents


def _post(url, body, retries=5):
    """POST JSON to url, retrying transient failures with exponential backoff."""
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            detail = e.read().decode(errors="replace")[:400]
            raise RuntimeError(f"Gemini API error {e.code}: {detail}")
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise
    raise RuntimeError("exhausted retries contacting Gemini")


def complete(model, system, messages, tools):
    """Run one Gemini generateContent call. Returns {"text", "tool_calls",
    "usage"}, where tool_calls is [{"name", "args", "signature"}] and usage
    is {"input", "output"} token counts.
    """
    url = f"{API_ROOT}/{model}:generateContent?key={api_key()}"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _to_wire(messages),
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 65536},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": [t["schema"] for t in tools]}]

    raw = _post(url, body)
    parts = raw["candidates"][0].get("content", {}).get("parts", [])

    # Thinking parts carry the model's private reasoning; never surface them.
    text = "".join(
        p["text"] for p in parts if "text" in p and not p.get("thought")
    )
    tool_calls = [
        {
            "name": p["functionCall"]["name"],
            "args": p["functionCall"].get("args", {}),
            "signature": p.get("thoughtSignature"),
        }
        for p in parts
        if "functionCall" in p
    ]

    usage_raw = raw.get("usageMetadata", {})
    usage = {
        "input": usage_raw.get("promptTokenCount", 0),
        "output": usage_raw.get("candidatesTokenCount", 0),
    }
    return {"text": text, "tool_calls": tool_calls, "usage": usage}
