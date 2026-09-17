"""Small bounded LAB traffic source used to create real HAProxy evidence."""

from __future__ import annotations

import http.client
import json
import os
import time
from collections import Counter


TARGET_HOST = os.environ.get("TARGET_HOST", "traffic-haproxy")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "8080"))
REQUESTS_PER_SECOND = min(60, max(1, int(os.environ.get("REQUESTS_PER_SECOND", "40"))))
ROUTES = ("public", "auth", "catalog", "checkout")


def main() -> None:
    interval = 1.0 / REQUESTS_PER_SECOND
    counts: Counter[str] = Counter()
    next_request = time.monotonic()
    next_report = next_request + 10
    sequence = 0
    while True:
        route = ROUTES[sequence % len(ROUTES)]
        sequence += 1
        connection = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=1.5)
        try:
            connection.request(
                "GET",
                f"/{route}?source=bounded-lab",
                headers={"X-Request-ID": f"lab-{sequence:012d}", "Connection": "close"},
            )
            response = connection.getresponse()
            response.read()
            counts[f"{route}:{response.status // 100}xx"] += 1
        except OSError:
            counts[f"{route}:connection_error"] += 1
        finally:
            connection.close()
        now = time.monotonic()
        if now >= next_report:
            print(json.dumps({"event": "traffic_window", "seconds": 10, "outcomes": counts}, separators=(",", ":")), flush=True)
            counts.clear()
            next_report = now + 10
        next_request += interval
        time.sleep(max(0.0, next_request - time.monotonic()))


if __name__ == "__main__":
    main()
