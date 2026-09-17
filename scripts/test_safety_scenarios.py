#!/usr/bin/env python3
"""Black-box safety acceptance for non-flagship deterministic classes."""

from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime

from test_vertical_slice import BASE_URL, ENVIRONMENT_ID, ROOT, Client, wait_for


def main() -> int:
    client = Client()
    password = (ROOT / ".secrets/bootstrap_password").read_text(encoding="utf-8").strip()
    _, login = client.request("POST", "/api/v1/auth/login", body={"email": "researcher@shlb.local", "password": password})
    client.csrf = login["data"]["csrf_token"]
    print("PASS: authenticated Researcher for safety scenarios")

    def actions() -> list[dict]:
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/actions")
        return payload["data"]["items"]

    def create_fault(scenario: str) -> dict:
        key = uuid.uuid4().hex
        _, payload = client.request(
            "POST",
            f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults",
            body={"scenario": scenario, "duration_seconds": 120},
            headers=client.mutation_headers(f"inject-{key}"),
            expected=202,
        )
        fault = payload["data"]

        def active() -> dict | None:
            _, response = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults")
            row = next(item for item in response["data"]["items"] if item["id"] == fault["id"])
            return row if row["status"] == "ACTIVE" else None

        return wait_for(f"{scenario} ground truth applied", active, timeout=30)

    def incident_for(classification: str, opened_after: float) -> dict | None:
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/incidents")
        candidates = [
            item for item in payload["data"]["items"]
            if item["classification"] == classification
            and item["status"] != "RESOLVED"
            and datetime.fromisoformat(item["opened_at"]).timestamp() >= opened_after - 5
        ]
        return candidates[0] if candidates else None

    def clear_fault(fault: dict) -> None:
        _, response = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults")
        current = next(item for item in response["data"]["items"] if item["id"] == fault["id"])
        client.request("DELETE", f"/api/v1/lab/faults/{fault['id']}", headers=client.mutation_headers(f"clear-{uuid.uuid4().hex}", version=current["version"]), expected=202)

    def resolved(incident_id: str) -> dict | None:
        _, payload = client.request("GET", f"/api/v1/incidents/{incident_id}")
        return payload["data"] if payload["data"]["status"] == "RESOLVED" else None

    for scenario, expected_class in (("UNKNOWN_CONFLICT", "UNKNOWN"), ("SHARED_CHECKOUT_FAILURE", "SHARED_ROUTE_FAILURE")):
        action_ids_before = {item["id"] for item in actions()}
        opened_after = time.time()
        fault = create_fault(scenario)
        incident = wait_for(f"{expected_class} incident persisted", lambda: incident_for(expected_class, opened_after), timeout=45)
        time.sleep(6)
        new_actions = [item for item in actions() if item["id"] not in action_ids_before]
        assert not new_actions, f"{expected_class} unexpectedly prepared destructive actions: {new_actions}"
        print(f"PASS: {expected_class} performed no HAProxy mutation")
        clear_fault(fault)
        wait_for(f"{expected_class} incident resolved after cleanup", lambda: resolved(incident["id"]), timeout=45)

    opened_after = time.time()
    fault = create_fault("INST_B_DOWN")
    incident = wait_for("INSTANCE_DOWN incident persisted", lambda: incident_for("INSTANCE_DOWN", opened_after), timeout=45)

    def instance_action() -> dict | None:
        matches = [item for item in actions() if item["incident_id"] == incident["id"]]
        return matches[0] if matches and matches[0]["lifecycle"] == "COMMITTED" else None

    action = wait_for("instance-wide action verified and committed", instance_action, timeout=75)
    assert action["kind"] == "INSTANCE_QUARANTINE"
    _, matrix = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/matrix")
    cells = matrix["data"]["cells"]
    b_cells = [item for item in cells if item["instance"] == "inst-b"]
    peer_cells = [item for item in cells if item["instance"] != "inst-b"]
    assert len(b_cells) == 4 and all(item["desired"] == {"admin": "drain", "weight": 0} for item in b_cells)
    assert all(item["observed"]["admin_state"] == "drain" and item["observed"]["weight"] == 0 for item in b_cells)
    assert all(item["observed"]["admin_state"] == "ready" and item["observed"]["weight"] == 100 for item in peer_cells)
    print("PASS: INSTANCE_DOWN drained exactly four B memberships and preserved all eight physical peers")

    clear_fault(fault)
    wait_for("INSTANCE_DOWN probe-gated restore resolved", lambda: resolved(incident["id"]), timeout=60)
    _, final_matrix = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/matrix")
    assert all(item["desired"] == {"admin": "ready", "weight": 100} and item["observed"]["admin_state"] == "ready" and item["observed"]["weight"] == 100 for item in final_matrix["data"]["cells"])
    print("PASS: instance recovery restored all memberships after three healthy direct-probe windows")
    print("PASS: safety scenario suite completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
