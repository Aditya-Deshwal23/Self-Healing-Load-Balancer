"""Small bounded LAB traffic source used to create real HAProxy evidence."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any


TARGET_HOST = os.environ.get("TARGET_HOST", "traffic-haproxy")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "8080"))
HARD_REQUESTS_PER_SECOND_CEILING = 60
REQUESTS_PER_SECOND_CAP = min(
    HARD_REQUESTS_PER_SECOND_CEILING,
    max(1, int(os.environ.get("MAX_REQUESTS_PER_SECOND", "60"))),
)
DEFAULT_REQUESTS_PER_SECOND = min(
    REQUESTS_PER_SECOND_CAP,
    max(1, int(os.environ.get("REQUESTS_PER_SECOND", "40"))),
)
ROUTES = tuple(
    route.strip().strip("/")
    for route in os.environ.get("TRAFFIC_ROUTES", "public,auth,catalog,checkout").split(",")
    if route.strip().strip("/")
)
CONNECTION_POOL_SIZE = max(1, int(os.environ.get("TRAFFIC_CONNECTION_POOL_SIZE", "32")))
PROFILE_NAME = os.environ.get("TRAFFIC_PROFILE", "steady")


@dataclass(frozen=True)
class Phase:
    routes: tuple[str, ...]
    requests_per_second: int
    duration_seconds: float


NAMED_PROFILES: dict[str, tuple[dict[str, Any], ...]] = {
    "steady": (
        {"routes": "all", "requests_per_second": DEFAULT_REQUESTS_PER_SECOND, "duration_seconds": 0},
    ),
    "ramp": (
        {"routes": "all", "requests_per_second": 10, "duration_seconds": 30},
        {"routes": "all", "requests_per_second": 40, "duration_seconds": 30},
        {"routes": "all", "requests_per_second": 60, "duration_seconds": 30},
    ),
    "burst": (
        {"routes": "all", "requests_per_second": 10, "duration_seconds": 30},
        {"routes": "all", "requests_per_second": 60, "duration_seconds": 30},
        {"routes": "all", "requests_per_second": 10, "duration_seconds": 30},
    ),
}


def _phase_routes(value: str | list[str]) -> tuple[str, ...]:
    if value == "all":
        return ROUTES
    if isinstance(value, str):
        routes = tuple(route.strip().strip("/") for route in value.split(",") if route.strip().strip("/"))
    else:
        routes = tuple(route.strip().strip("/") for route in value if route.strip().strip("/"))
    if not routes or any(route not in ROUTES for route in routes):
        raise ValueError("profile routes must be non-empty and drawn from TRAFFIC_ROUTES")
    return routes


def load_profile() -> tuple[Phase, ...]:
    raw_profile = os.environ.get("TRAFFIC_PROFILE_JSON")
    if raw_profile:
        configured = json.loads(raw_profile)
    else:
        configured = NAMED_PROFILES.get(PROFILE_NAME)
        if configured is None:
            raise ValueError(f"unknown traffic profile: {PROFILE_NAME}")
    if not isinstance(configured, list | tuple) or not configured:
        raise ValueError("traffic profile must contain at least one phase")
    phases = []
    for item in configured:
        if not isinstance(item, dict):
            raise ValueError("traffic profile phases must be objects")
        requests_per_second = min(
            REQUESTS_PER_SECOND_CAP,
            max(1, int(item["requests_per_second"])),
        )
        duration_seconds = float(item["duration_seconds"])
        if duration_seconds < 0:
            raise ValueError("phase duration_seconds cannot be negative")
        phases.append(Phase(_phase_routes(item.get("routes", "all")), requests_per_second, duration_seconds))
    return tuple(phases)


def _request(route: str, sequence: int) -> str:
    connection = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=1.5)
    try:
        connection.request(
            "GET",
            f"/{route}?source=bounded-lab",
            headers={"X-Request-ID": f"lab-{sequence:012d}", "Connection": "close"},
        )
        response = connection.getresponse()
        response.read()
        return f"{route}:{response.status // 100}xx"
    except OSError:
        return f"{route}:connection_error"
    finally:
        connection.close()


async def _dispatch(
    route: str,
    sequence: int,
    counts: Counter[str],
    semaphore: asyncio.Semaphore,
    executor: ThreadPoolExecutor,
) -> None:
    async with semaphore:
        outcome = await asyncio.get_running_loop().run_in_executor(executor, _request, route, sequence)
        counts[outcome] += 1


async def _report(counts: Counter[str]) -> None:
    while True:
        await asyncio.sleep(10)
        print(json.dumps({"event": "traffic_window", "seconds": 10, "outcomes": counts}, separators=(",", ":")), flush=True)
        counts.clear()


async def _run_phase(
    phase: Phase,
    counts: Counter[str],
    semaphore: asyncio.Semaphore,
    executor: ThreadPoolExecutor,
    sequence: int,
) -> int:
    interval = 1.0 / phase.requests_per_second
    started = time.monotonic()
    next_request = started
    pending: set[asyncio.Task[None]] = set()
    while phase.duration_seconds == 0 or time.monotonic() - started < phase.duration_seconds:
        now = time.monotonic()
        while now >= next_request:
            route = phase.routes[sequence % len(phase.routes)]
            sequence += 1
            task = asyncio.create_task(_dispatch(route, sequence, counts, semaphore, executor))
            pending.add(task)
            task.add_done_callback(pending.discard)
            next_request += interval
            now = time.monotonic()
        await asyncio.sleep(min(0.05, max(0.0, next_request - time.monotonic())))
    if pending:
        await asyncio.gather(*pending)
    return sequence


async def run() -> None:
    phases = load_profile()
    counts: Counter[str] = Counter()
    semaphore = asyncio.Semaphore(CONNECTION_POOL_SIZE)
    reporter = asyncio.create_task(_report(counts))
    executor = ThreadPoolExecutor(max_workers=CONNECTION_POOL_SIZE)
    sequence = 0
    try:
        for phase in phases:
            sequence = await _run_phase(phase, counts, semaphore, executor, sequence)
    finally:
        reporter.cancel()
        await asyncio.gather(reporter, return_exceptions=True)
        executor.shutdown(wait=True)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
