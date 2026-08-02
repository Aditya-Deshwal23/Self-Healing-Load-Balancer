"""Deterministic black-box HTTP target for the isolated Phase 1 lab."""

from __future__ import annotations

import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


INSTANCE_ID = os.environ.get("INSTANCE_ID", "inst-unknown")
VERSION_ID = os.environ.get("VERSION_ID", "demo-v1")
ALLOWED_ROUTES = frozenset({"public", "auth", "catalog", "checkout"})


class Handler(BaseHTTPRequestHandler):
    server_version = "shlb-demo/1"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        self._serve(include_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler contract
        self._serve(include_body=False)

    def _serve(self, *, include_body: bool) -> None:
        started = time.monotonic()
        path = urlsplit(self.path).path

        if path == "/healthz":
            status = HTTPStatus.OK
            payload = {"status": "ok", "instance": INSTANCE_ID, "version": VERSION_ID}
        else:
            route = path.strip("/").split("/", 1)[0]
            if route in ALLOWED_ROUTES:
                status = HTTPStatus.OK
                payload = {
                    "instance": INSTANCE_ID,
                    "version": VERSION_ID,
                    "route": route,
                    "path": path,
                    "request_id": self.headers.get("X-Request-ID"),
                }
            else:
                status = HTTPStatus.NOT_FOUND
                payload = {"error": "unmapped_route", "path": path}

        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

        event = {
            "timestamp_ns": time.time_ns(),
            "request_id": self.headers.get("X-Request-ID"),
            "instance": INSTANCE_ID,
            "version": VERSION_ID,
            "method": self.command,
            "path": path,
            "status": int(status),
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
        }
        print(json.dumps(event, separators=(",", ":")), flush=True)

    def log_message(self, format: str, *args: object) -> None:
        # Access events are emitted as bounded structured JSON by _serve().
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

