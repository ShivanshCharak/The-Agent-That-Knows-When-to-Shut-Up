"""Loopback-only HTTP service used by the VS Code extension."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from threading import Lock
import time
from urllib.parse import urlparse

from adapters.base import Event
from gate.bedrock import BedrockResponder
from gate.context import ContextBuilder
from gate.decider import HttpDecider
from gate.gate import GateConfig, InterjectionGate
from gate.handler import InterjectionHandler
from gate.rules import should_skip


MAX_BODY_BYTES = 128_000
MAX_FILE_CHARS = 12_000
context_builder = ContextBuilder()
threshold = float(os.environ.get("INTERJECTION_THRESHOLD", "0.7"))
decider_username = os.environ.get("DECIDER_USERNAME")
decider_password = os.environ.get("DECIDER_PASSWORD")
if bool(decider_username) != bool(decider_password):
    raise ValueError("Set both DECIDER_USERNAME and DECIDER_PASSWORD, or neither")
decider_auth = (decider_username, decider_password) if decider_username else None
decider_url = os.environ.get("DECIDER_URL", "http://localhost:8000")
parsed_decider_url = urlparse(decider_url)
is_loopback = parsed_decider_url.hostname in {"localhost", "127.0.0.1", "::1"}
if not is_loopback and (parsed_decider_url.scheme != "https" or decider_auth is None):
    raise ValueError("Remote DECIDER_URLs require HTTPS and DECIDER_USERNAME/DECIDER_PASSWORD")
decider = HttpDecider(decider_url, auth=decider_auth)

responder = None
bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID")
if bedrock_model_id:
    responder = BedrockResponder(bedrock_model_id, region=os.environ.get("AWS_REGION"))

core = InterjectionHandler(
    decider=decider,
    gate=InterjectionGate(GateConfig(threshold=threshold)),
    responder=responder,
)
event_lock = Lock()


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "InterjectionBridge/0.1"

    def _send(self, status: int, body: dict) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if urlparse(self.path).path != "/health":
            self._send(404, {"error": "not found"})
            return
        self._send(200, {
            "ok": True,
            "decider": "http",
            "threshold": threshold,
            "bedrock_enabled": responder is not None,
        })

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/event":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                self._send(413, {"error": "request must be between 1 byte and 128 KB"})
                return
            body = json.loads(self.rfile.read(length))
            kind = body["kind"]
            if kind not in {"file_open", "edit", "test_fail", "test_pass", "inspect_error", "idle"}:
                self._send(400, {"error": "unsupported event kind"})
                return
            payload = body.get("payload", {})
            if not isinstance(payload, dict):
                self._send(400, {"error": "payload must be an object"})
                return
            content = payload.get("content")
            if isinstance(content, str) and len(content) > MAX_FILE_CHARS:
                payload["content"] = content[:MAX_FILE_CHARS]
                payload["content_truncated"] = True
            event = Event(ts=float(body.get("ts", time.time())), kind=kind, payload=payload)
            with event_lock:
                context_builder.update(event)
                if should_skip(event):
                    result = None
                else:
                    result = core.handle(context_builder.snapshot(event.ts))
                    if result.allowed:
                        context_builder.mark_spoke(event.ts)
            if result is None:
                self._send(200, {"skipped": True, "reason": "rule_skipped"})
                return
            self._send(200, {
                "skipped": False,
                "decision": {
                    "speak": result.decision.speak,
                    "kind": result.decision.kind,
                    "confidence": result.decision.confidence,
                },
                "allowed": result.allowed,
                "reason": result.reason,
                "response": result.response,
                "bedrock_called": result.bedrock_called,
            })
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"invalid event: {exc}"})
        except Exception as exc:
            self._send(502, {"error": str(exc)})

    def log_message(self, format: str, *args) -> None:
        print(f"[bridge] {self.address_string()} {format % args}")


def main() -> None:
    host = "127.0.0.1"
    port = int(os.environ.get("INTERJECTION_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), BridgeHandler)
    print(f"Interjection bridge listening at http://{host}:{port}")
    print(f"Mode: {decider_mode}; threshold: {threshold}; Bedrock: {'enabled' if responder else 'off'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping interjection bridge")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
