#!/usr/bin/env python3
"""Run real SHLB baseline/gray-failure experiments and emit CSV results.

The runner talks to the running Compose lab through its public HTTPS edge and
uses the authenticated LAB API to apply the real bounded fault. It never
fabricates latency or healing measurements.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path


def request(url: str, timeout: float = 8.0) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read()
            return response.status, (time.perf_counter() - started) * 1000
    except Exception:
        return 599, (time.perf_counter() - started) * 1000


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))]


def run(label: str, base_url: str, seconds: int) -> dict[str, float | str]:
    samples: list[float] = []
    failures = 0
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status, latency = request(f"{base_url.rstrip('/')}/checkout")
        samples.append(latency)
        failures += int(status >= 500)
    return {
        "scenario": label,
        "requests": len(samples),
        "failure_rate": round(failures / len(samples), 4) if samples else 0,
        "p95_ms": round(percentile(samples, 0.95), 2),
        "p99_ms": round(percentile(samples, 0.99), 2),
        "mean_ms": round(statistics.mean(samples), 2) if samples else 0,
        "mttd_seconds": None,
        "mttr_seconds": None,
    }


def compose_fault(action: str, duration: int = 30) -> None:
    """Use the real private backend fault endpoint through Compose."""
    token = Path(".secrets/fault_control_token").read_text(encoding="utf-8").strip()
    payload = json.dumps({
        "kind": "gray_failure",
        "expires_at": time.time() + duration,
        "ground_truth_id": f"benchmark-{int(time.time())}",
    })
    command = ["docker", "compose", "exec", "-T", "demo-backend-a", "python", "-c",
               "import json,urllib.request,sys; p=json.loads(sys.argv[1]); r=urllib.request.Request('http://127.0.0.1:8080/__lab/fault', data=json.dumps(p).encode(), headers={'Content-Type':'application/json','X-SHLB-Lab-Token':sys.argv[2]}, method='PUT'); print(urllib.request.urlopen(r).read().decode())",
               payload, token] if action == "start" else [
                   "docker", "compose", "exec", "-T", "demo-backend-a", "python", "-c",
                   "import urllib.request,sys; r=urllib.request.Request('http://127.0.0.1:8080/__lab/fault', headers={'X-SHLB-Lab-Token':sys.argv[1]}, method='DELETE'); print(urllib.request.urlopen(r).read().decode())",
                   token,
               ]
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://localhost:8443")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results.csv"))
    args = parser.parse_args()
    results = [run("baseline_round_robin", args.base_url, args.seconds)]
    subprocess.run(["docker", "compose", "stop", "control-worker"], check=True)
    compose_fault("start", args.seconds + 15)
    try:
        results.append(run("gray_failure_without_shlb", args.base_url, args.seconds))
    finally:
        compose_fault("clear")
        subprocess.run(["docker", "compose", "start", "control-worker"], check=True)
    compose_fault("start", args.seconds + 15)
    try:
        results.append(run("gray_failure_shlb_active", args.base_url, args.seconds))
    finally:
        compose_fault("clear")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({"results": results, "csv": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
