#!/usr/bin/env python3
"""Black-box acceptance for the reachable, multi-route degraded-instance class."""

from __future__ import annotations

import sys
import time
import uuid

from test_vertical_slice import ENVIRONMENT_ID, ROOT, Client, wait_for


def main() -> int:
    client = Client()
    password = (ROOT / ".secrets/bootstrap_password").read_text(encoding="utf-8").strip()
    _, login = client.request("POST", "/api/v1/auth/login", body={"email": "researcher@shlb.local", "password": password})
    client.csrf = login["data"]["csrf_token"]

    run_key = uuid.uuid4().hex
    _, created = client.request(
        "POST",
        f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults",
        body={"scenario": "INSTANCE_B_DEGRADED", "duration_seconds": 180},
        headers=client.mutation_headers(f"inject-{run_key}"),
        expected=202,
    )
    fault_id = created["data"]["id"]

    def active_fault() -> dict | None:
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults")
        row = next(item for item in payload["data"]["items"] if item["id"] == fault_id)
        return row if row["status"] == "ACTIVE" else None

    wait_for("degraded LAB ground truth applied", active_fault, timeout=30)
    for route in ("public", "auth"):
        for sample in range(12):
            client.request("GET", f"/{route}?degraded={sample}")

    def incident() -> dict | None:
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/incidents")
        matches = [item for item in payload["data"]["items"] if item["classification"] == "INSTANCE_DEGRADED" and item["status"] != "RESOLVED"]
        return matches[0] if matches else None

    current_incident = wait_for("INSTANCE_DEGRADED incident persisted", incident, timeout=60)

    def action() -> dict | None:
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/actions")
        matches = [item for item in payload["data"]["items"] if item["incident_id"] == current_incident["id"]]
        return matches[0] if matches else None

    selected = wait_for("bounded INSTANCE_WEIGHT action planned", action, timeout=30)
    assert selected["kind"] == "INSTANCE_WEIGHT"
    assert selected["requested_state"]["admin_state"] == "ready"
    assert selected["requested_state"]["weight"] < 100
    _, action_detail = client.request("GET", f"/api/v1/actions/{selected['id']}")
    first_attempt = action_detail["data"]["attempts"][0]
    assert all(
        state["admin_state"] == "ready" and state["weight"] == 50
        for state in first_attempt["observed_state"]["targets"].values()
    )

    _, matrix = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/matrix")
    cells = [item for item in matrix["data"]["cells"] if item["instance"] == "inst-b"]
    assert cells and all(item["observed"]["admin_state"] != "drain" for item in cells)
    print("PASS: reachable multi-route degradation first reduced instance weight without draining")

    _, all_cells = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/matrix")
    assert all(item["observed"]["admin_state"] != "drain" for item in all_cells if item["instance"] == "inst-b")

    fault = active_fault()
    client.request(
        "DELETE",
        f"/api/v1/lab/faults/{fault_id}",
        headers=client.mutation_headers(f"clear-{run_key}", version=fault["version"]),
        expected=202,
    )
    time.sleep(2)
    print("PASS: INSTANCE_DEGRADED scenario cleanup requested")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
