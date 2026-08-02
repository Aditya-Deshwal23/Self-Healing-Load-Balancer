#!/usr/bin/env python3
"""Repeatable black-box acceptance test for the flagship LAB journey."""

from __future__ import annotations

import http.cookiejar
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://localhost:8443"
ENVIRONMENT_ID = "40000000-0000-4000-8000-000000000001"


class Client:
    def __init__(self) -> None:
        self.cookies = http.cookiejar.CookieJar()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPSHandler(context=context),
        )
        self.csrf = ""
        self.counter = 0

    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None, expected: int = 200) -> tuple[Any, Any]:
        self.counter += 1
        request_headers = {"Accept": "application/json", "X-Request-ID": f"vertical-slice-{self.counter:04d}", **(headers or {})}
        encoded = None
        if body is not None:
            encoded = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{BASE_URL}{path}", data=encoded, headers=request_headers, method=method)
        try:
            response = self.opener.open(request, timeout=8)
            raw = response.read()
        except urllib.error.HTTPError as exc:
            response = exc
            raw = exc.read()
        parsed = json.loads(raw) if raw else None
        if response.status != expected:
            raise AssertionError(f"{method} {path}: expected {expected}, received {response.status}: {str(parsed)[:1000]}")
        return response, parsed

    def mutation_headers(self, key: str, *, version: int | None = None) -> dict[str, str]:
        headers = {"Origin": BASE_URL, "X-CSRF-Token": self.csrf, "Idempotency-Key": key}
        if version is not None:
            headers["If-Match"] = f'"{version}"'
        return headers


def wait_for(label: str, callback: Callable[[], Any], *, timeout: float = 90) -> Any:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = callback()
        if last:
            print(f"PASS: {label}")
            return last
        time.sleep(2)
    raise AssertionError(f"timed out waiting for {label}; last observation: {last!r}")


def main() -> int:
    client = Client()
    password = (ROOT / ".secrets/bootstrap_password").read_text(encoding="utf-8").strip()
    _, login = client.request("POST", "/api/v1/auth/login", body={"email": "researcher@shlb.local", "password": password})
    client.csrf = login["data"]["csrf_token"]
    assert login["data"]["scopes"][0]["role"] == "RESEARCHER"
    print("PASS: authenticated seeded Researcher")

    run_key = uuid.uuid4().hex
    _, created = client.request(
        "POST",
        f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults",
        body={"scenario": "CHECKOUT_INST_B_FAILURE", "duration_seconds": 180},
        headers=client.mutation_headers(f"inject-{run_key}"),
        expected=202,
    )
    fault_id = created["data"]["id"]

    def active_fault():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults")
        row = next(item for item in payload["data"]["items"] if item["id"] == fault_id)
        return row if row["status"] == "ACTIVE" else None

    wait_for("worker applied independent LAB ground truth", active_fault, timeout=30)

    def classified_incident():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/incidents")
        matches = [item for item in payload["data"]["items"] if item["classification"] == "ROUTE_INSTANCE_FAILURE" and item["status"] != "RESOLVED"]
        return matches[0] if matches else None

    incident = wait_for("real ROUTE_INSTANCE_FAILURE incident persisted", classified_incident, timeout=45)

    def selected_action():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/actions")
        matches = [item for item in payload["data"]["items"] if item["incident_id"] == incident["id"]]
        return matches[0] if matches else None

    action = wait_for("durable route-local action planned", selected_action, timeout=30)

    def committed_action():
        _, payload = client.request("GET", f"/api/v1/actions/{action['id']}")
        return payload["data"] if payload["data"]["lifecycle"] == "COMMITTED" else None

    action = wait_for("HAProxy readback and EFFECTIVE verification committed", committed_action, timeout=60)
    assert action["target"] == {"backend": "be_checkout", "server": "srv_inst_b"}
    assert action["attempts"][0]["status"] in {"CONFIRMED", "ACKNOWLEDGEMENT_LOST_CONFIRMED"}

    _, matrix = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/matrix")
    cells = {(item["route"], item["instance"]): item for item in matrix["data"]["cells"]}
    target = cells[("checkout", "inst-b")]
    assert target["desired"] == {"admin": "drain", "weight": 0}
    assert target["observed"]["admin_state"] == "drain" and target["observed"]["weight"] == 0
    for route in ("public", "auth", "catalog"):
        sibling = cells[(route, "inst-b")]
        assert sibling["observed"]["admin_state"] == "ready" and sibling["observed"]["weight"] == 100
    print("PASS: only checkout/inst-b changed; inst-b sibling routes remain ready")

    observed_instances: dict[str, set[str]] = {route: set() for route in ("public", "auth", "catalog", "checkout")}
    for route in observed_instances:
        for sample in range(18):
            _, payload = client.request("GET", f"/{route}?acceptance={sample}")
            observed_instances[route].add(payload["instance"])
    for route in ("public", "auth", "catalog"):
        assert "inst-b" in observed_instances[route]
    assert "inst-b" not in observed_instances["checkout"]
    print("PASS: real request outcomes preserve inst-b on unaffected routes and exclude it only from checkout")

    current_fault = active_fault()
    client.request(
        "DELETE",
        f"/api/v1/lab/faults/{fault_id}",
        headers=client.mutation_headers(f"clear-{run_key}", version=current_fault["version"]),
        expected=202,
    )

    def completed_reintegration():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/reintegration")
        matches = [item for item in payload["data"]["items"] if item["action_id"] == action["id"]]
        return matches[0] if matches and matches[0]["status"] == "COMPLETED" else None

    recovery = wait_for("PROBING → 5% → 20% → 50% → 100% → HEALTHY completed", completed_reintegration, timeout=120)
    _, recovery_detail = client.request("GET", f"/api/v1/reintegration/{recovery['id']}")
    assert [stage["name"] for stage in recovery_detail["data"]["stages"]] == ["PROBING", "5%", "20%", "50%", "100%", "HEALTHY"]
    assert all(stage["status"] == "VERIFIED" for stage in recovery_detail["data"]["stages"])
    _, resolved = client.request("GET", f"/api/v1/incidents/{incident['id']}")
    assert resolved["data"]["status"] == "RESOLVED"
    _, final_matrix = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/matrix")
    final_target = next(item for item in final_matrix["data"]["cells"] if item["route"] == "checkout" and item["instance"] == "inst-b")
    assert final_target["desired"] == {"admin": "ready", "weight": 100}
    assert final_target["observed"]["admin_state"] == "ready" and final_target["observed"]["weight"] == 100
    print("PASS: incident resolved and checkout/inst-b returned to ready weight 100")
    print("PASS: flagship real vertical slice completed end to end")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
