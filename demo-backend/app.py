"""Deterministic LAB target with bounded metrics and an internal-only fault surface."""

from __future__ import annotations

import hmac
import json
import os
import threading
import time
import random
from collections import defaultdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


INSTANCE_ID = os.environ.get("INSTANCE_ID", "inst-unknown")
VERSION_ID = os.environ.get("VERSION_ID", "demo-v1")
ALLOWED_ROUTES = frozenset({"public", "auth", "catalog", "checkout"})
FAULT_TOKEN_FILE = Path(os.environ.get("FAULT_TOKEN_FILE", "/run/secrets/fault_control_token"))


def _read_fault_token() -> str:
    try:
        token = FAULT_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return token if len(token) >= 24 else ""


FAULT_TOKEN = _read_fault_token()
STATE_LOCK = threading.RLock()
FAULT: dict[str, object] | None = None
REQUESTS: defaultdict[tuple[str, str], int] = defaultdict(int)
LATENCY_SECONDS: defaultdict[str, float] = defaultdict(float)
LATENCY_BUCKET_BOUNDS = (0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
LATENCY_BUCKETS: defaultdict[tuple[str, float], int] = defaultdict(int)


def _active_fault() -> dict[str, object] | None:
    global FAULT
    with STATE_LOCK:
        if FAULT and float(FAULT["expires_at"]) <= time.time():
            FAULT = None
        return dict(FAULT) if FAULT else None


def _status_family(status: HTTPStatus) -> str:
    return f"{int(status) // 100}xx"


def _prometheus() -> bytes:
    with STATE_LOCK:
        request_rows = sorted(REQUESTS.items())
        latency_rows = sorted(LATENCY_SECONDS.items())
        bucket_rows = sorted(LATENCY_BUCKETS.items())
    fault = _active_fault()
    identity = f'instance="{INSTANCE_ID}",version="{VERSION_ID}"'
    lines = [
        "# HELP shlb_backend_requests_total Real application requests handled by a demo backend.",
        "# TYPE shlb_backend_requests_total counter",
    ]
    for (route, family), value in request_rows:
        lines.append(
            f'shlb_backend_requests_total{{{identity},route="{route}",status_family="{family}"}} {value}'
        )
    lines.extend(
        [
            "# HELP shlb_backend_request_duration_seconds Application request latency histogram.",
            "# TYPE shlb_backend_request_duration_seconds histogram",
        ]
    )
    for (route, bound), value in bucket_rows:
        lines.append(f'shlb_backend_request_duration_seconds_bucket{{{identity},route="{route}",le="{bound:g}"}} {value}')
    for route in ALLOWED_ROUTES:
        count = sum(value for (observed_route, _family), value in request_rows if observed_route == route)
        lines.append(f'shlb_backend_request_duration_seconds_bucket{{{identity},route="{route}",le="+Inf"}} {count}')
        lines.append(f'shlb_backend_request_duration_seconds_count{{{identity},route="{route}"}} {count}')
        lines.append(f'shlb_backend_request_duration_seconds_sum{{{identity},route="{route}"}} {dict(latency_rows).get(route, 0):.9f}')
    lines.extend(
        [
            "# HELP shlb_backend_fault_active Whether a bounded LAB fault is currently active.",
            "# TYPE shlb_backend_fault_active gauge",
            f'shlb_backend_fault_active{{{identity},kind="{fault["kind"] if fault else "none"}"}} {1 if fault else 0}',
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "shlb-demo/3"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        self._serve(include_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler contract
        self._serve(include_body=False)

    def do_PUT(self) -> None:  # noqa: N802 - stdlib handler contract
        if urlsplit(self.path).path != "/__lab/fault":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorized_lab_request():
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise ValueError("invalid body length")
            payload = json.loads(self.rfile.read(length))
            kind = str(payload["kind"])
            route = payload.get("route")
            expires_at = float(payload["expires_at"])
            ground_truth_id = str(payload["ground_truth_id"])
            if kind not in {"route_failure", "instance_down", "unknown_conflict", "gray_failure"}:
                raise ValueError("unsupported fault kind")
            if route is not None and route not in ALLOWED_ROUTES:
                raise ValueError("unsupported route")
            if kind == "route_failure" and route is None:
                raise ValueError("route is required")
            if expires_at <= time.time() or expires_at > time.time() + 900:
                raise ValueError("expiry outside LAB bound")
            if len(ground_truth_id) > 80:
                raise ValueError("ground truth ID too long")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid_fault_contract"})
            return
        global FAULT
        with STATE_LOCK:
            FAULT = {
                "kind": kind,
                "route": route,
                "expires_at": expires_at,
                "ground_truth_id": ground_truth_id,
            }
        self._json(HTTPStatus.OK, {"status": "active", "instance": INSTANCE_ID, "fault": FAULT})

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler contract
        if urlsplit(self.path).path != "/__lab/fault" or not self._authorized_lab_request():
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        global FAULT
        with STATE_LOCK:
            previous = FAULT
            FAULT = None
        self._json(
            HTTPStatus.OK,
            {"status": "cleared", "instance": INSTANCE_ID, "ground_truth_id": (previous or {}).get("ground_truth_id")},
        )

    def _authorized_lab_request(self) -> bool:
        supplied = self.headers.get("X-SHLB-Lab-Token", "")
        return bool(FAULT_TOKEN) and hmac.compare_digest(supplied, FAULT_TOKEN)

    def _serve(self, *, include_body: bool) -> None:
        started = time.monotonic()
        path = urlsplit(self.path).path
        fault = _active_fault()

        if path == "/metrics":
            body = _prometheus()
            self._raw(HTTPStatus.OK, body, "text/plain; version=0.0.4; charset=utf-8", include_body)
            return

        if path == "/__lab/status":
            if not self._authorized_lab_request():
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"}, include_body=include_body)
                return
            self._json(HTTPStatus.OK, {"instance": INSTANCE_ID, "fault": fault}, include_body=include_body)
            return

        if path.startswith("/__lab/probe/"):
            if not self._authorized_lab_request():
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"}, include_body=include_body)
                return
            route = path.rsplit("/", 1)[-1]
            failed = self._fault_affects(route, fault)
            gray = bool(fault and fault["kind"] == "gray_failure")
            if gray:
                time.sleep(0.12)
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE if failed else HTTPStatus.OK,
                {"instance": INSTANCE_ID, "route": route, "reachable": True, "application_ok": not failed},
                include_body=include_body,
            )
            return

        if path == "/healthz":
            failed = bool(fault and fault["kind"] == "instance_down")
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE if failed else HTTPStatus.OK,
                {"status": "failing" if failed else "ok", "instance": INSTANCE_ID, "version": VERSION_ID},
                include_body=include_body,
            )
            return

        route = path.strip("/").split("/", 1)[0]
        if route not in ALLOWED_ROUTES:
            self._json(HTTPStatus.NOT_FOUND, {"error": "unmapped_route", "path": path}, include_body=include_body)
            return

        failed = self._fault_affects(route, fault)
        gray = bool(fault and fault["kind"] == "gray_failure")
        if gray:
            time.sleep(0.5)
            failed = random.random() < 0.4
        status = HTTPStatus.INTERNAL_SERVER_ERROR if failed and gray else HTTPStatus.SERVICE_UNAVAILABLE if failed else HTTPStatus.OK
        payload = {
            "instance": INSTANCE_ID,
            "version": VERSION_ID,
            "route": route,
            "path": path,
            "request_id": self.headers.get("X-Request-ID"),
            "result": "lab_fault" if failed else "ok",
        }
        self._json(status, payload, include_body=include_body)
        elapsed = time.monotonic() - started
        with STATE_LOCK:
            REQUESTS[(route, _status_family(status))] += 1
            LATENCY_SECONDS[route] += elapsed
            for bound in LATENCY_BUCKET_BOUNDS:
                if elapsed <= bound:
                    LATENCY_BUCKETS[(route, bound)] += 1
        print(
            json.dumps(
                {
                    "timestamp_ns": time.time_ns(),
                    "instance": INSTANCE_ID,
                    "version": VERSION_ID,
                    "route": route,
                    "status_family": _status_family(status),
                    "duration_ms": round(elapsed * 1000, 3),
                },
                separators=(",", ":"),
            ),
            flush=True,
        )

    @staticmethod
    def _fault_affects(route: str, fault: dict[str, object] | None) -> bool:
        if not fault:
            return False
        if fault["kind"] == "instance_down":
            return True
        if fault["kind"] == "route_failure" and fault.get("route") == route:
            return True
        # UNKNOWN is intentionally conflicting: real traffic succeeds while the
        # persisted ground truth says the evidence channel is unreliable.
        return False

    def _json(self, status: HTTPStatus, payload: object, *, include_body: bool = True) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._raw(status, body, "application/json", include_body)

    def _raw(self, status: HTTPStatus, body: bytes, content_type: str, include_body: bool) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
