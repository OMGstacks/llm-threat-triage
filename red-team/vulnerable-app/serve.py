#!/usr/bin/env python3
"""OpenAI-compatible HTTP shim for the vulnerable app.

PyRIT, Garak, and Promptfoo all speak the OpenAI Chat Completions API, so exposing the mock
vulnerable agent at `/v1/chat/completions` lets those real tools attack it locally with **no API
key and no cost** — turning this range into an authorized live target for them.

Run:
    python3 red-team/vulnerable-app/serve.py            # vulnerable mode (default)
    VULN_APP_MODE=hardened python3 .../serve.py         # detector-backed guard enabled

Then point any OpenAI-compatible client at  http://127.0.0.1:8000/v1  with a dummy key.
The response includes a non-standard `x_acme` block carrying ground-truth exploit flags
(`leaked_secret` / `obeyed_injection` / `tool_invoked` / `refused`) for scoring; OpenAI clients
ignore unknown fields. Std-lib only.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "projects" / "llm-log-triage" / "src"))

from vulnerable_app import VulnerableAssistant  # noqa: E402

MODE = os.environ.get("VULN_APP_MODE", "vulnerable")


def _build_defense():
    """The same detector-backed input/output guard the assessment uses (for hardened mode)."""
    import detectors as det

    high = {"critical", "high"}

    def scan(source, role, content):
        ev = {"event_id": "shim", "source": source, "role": role, "content": content or ""}
        return [f for d in det.ALL_DETECTORS for f in d.scan(ev)]

    def defense(phase, **kw):
        if phase == "input":
            hot = [f for f in scan("chat_ui", "user", kw.get("user_message") or "") if f.severity in high]
            return (bool(hot), hot[0].detector if hot else "")
        hot = [f for f in scan("api", "assistant", kw.get("response") or "") if f.owasp_id.startswith(("LLM02", "LLM05"))]
        return (bool(hot), hot[0].detector if hot else "")

    return defense


def _make_agent():
    if MODE == "hardened":
        return VulnerableAssistant("hardened", defense=_build_defense())
    return VulnerableAssistant("vulnerable")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            return self._send(200, {"object": "list", "data": [{"id": "acme-assistant", "object": "model"}]})
        self._send(200, {"status": "ok", "mode": MODE})

    def do_POST(self):
        if not self.path.startswith("/v1/chat/completions"):
            return self._send(404, {"error": {"message": "not found"}})
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._send(400, {"error": {"message": "invalid JSON"}})
        messages = req.get("messages", [])
        user = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        if not user and messages:
            user = messages[-1].get("content", "")
        # tool/function messages are treated as untrusted retrieved context (enables indirect probes)
        untrusted = " ".join(m.get("content", "") for m in messages if m.get("role") in ("tool", "function")) or None

        turn = _make_agent().respond(user, untrusted)
        self._send(200, {
            "id": "chatcmpl-acme", "object": "chat.completion",
            "model": req.get("model", "acme-assistant"),
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": turn.response}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "x_acme": {"mode": MODE, "leaked_secret": turn.leaked_secret,
                       "obeyed_injection": turn.obeyed_injection,
                       "tool_invoked": turn.tool_invoked, "refused": turn.refused},
        })

    def log_message(self, *args):  # silence per-request stderr logging
        pass


def main() -> int:
    host = os.environ.get("VULN_APP_HOST", "127.0.0.1")
    port = int(os.environ.get("VULN_APP_PORT", "8000"))
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"vulnerable-app shim: http://{host}:{port}/v1  (mode={MODE})  POST /v1/chat/completions")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
