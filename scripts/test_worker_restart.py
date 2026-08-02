#!/usr/bin/env python3
"""Black-box proof that worker restarts do not duplicate or replay actions."""

from __future__ import annotations

import subprocess
import sys
import time
import uuid

from test_vertical_slice import BASE_URL, ENVIRONMENT_ID, ROOT, Client, wait_for


def restart_worker() -> None:
    subprocess.run(
        ["docker", "compose", "restart", "control-worker"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def main() -> int:
    client = Client()
    password = (ROOT / ".secrets/bootstrap_password").read_text(encoding="utf-8").strip()
    _, login = client.request(
        "POST",
        "/api/v1/auth/login",
        body={"email": "researcher@shlb.local", "password": password},
    )
    client.csrf = login["data"]["csrf_token"]
    run_key = uuid.uuid4().hex

    _, created = client.request(
        "POST",
        f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults",
        body={"scenario": "CHECKOUT_INST_B_FAILURE", "duration_seconds": 180},
        headers=client.mutation_headers(f"restart-inject-{run_key}"),
        expected=202,
    )
    fault_id = created["data"]["id"]

    def active_fault():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/lab/faults")
        row = next(item for item in payload["data"]["items"] if item["id"] == fault_id)
        return row if row["status"] == "ACTIVE" else None

    fault = wait_for("restart test fault became active", active_fault, timeout=30)

    def active_incident():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/incidents")
        matches = [
            item
            for item in payload["data"]["items"]
            if item["classification"] == "ROUTE_INSTANCE_FAILURE"
            and item["status"] != "RESOLVED"
        ]
        return matches[0] if matches else None

    incident = wait_for("restart test incident persisted", active_incident, timeout=45)

    def committed_action():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/actions")
        matches = [item for item in payload["data"]["items"] if item["incident_id"] == incident["id"]]
        if len(matches) != 1:
            return None
        return matches[0] if matches[0]["lifecycle"] == "COMMITTED" else None

    action = wait_for("restart test action committed once", committed_action, timeout=75)
    restart_worker()

    def worker_restarted():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/worker/status")
        return payload["data"] if payload["data"]["status"] == "ACTIVE" else None

    wait_for("worker reacquired sole-writer authority", worker_restarted, timeout=45)
    time.sleep(5)
    _, actions_after_restart = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/actions")
    incident_actions = [item for item in actions_after_restart["data"]["items"] if item["incident_id"] == incident["id"]]
    assert [item["id"] for item in incident_actions] == [action["id"]]
    print("PASS: restart under quarantine created no duplicate action")

    fault = active_fault()
    client.request(
        "DELETE",
        f"/api/v1/lab/faults/{fault_id}",
        headers=client.mutation_headers(f"restart-clear-{run_key}", version=fault["version"]),
        expected=202,
    )

    def active_reintegration():
        _, payload = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/reintegration")
        matches = [item for item in payload["data"]["items"] if item["action_id"] == action["id"]]
        return matches[0] if matches and matches[0]["status"] == "ACTIVE" else None

    recovery = wait_for("reintegration became active", active_reintegration, timeout=45)
    restart_worker()
    wait_for("worker restarted during recovery", worker_restarted, timeout=45)

    def completed_reintegration():
        _, payload = client.request("GET", f"/api/v1/reintegration/{recovery['id']}")
        return payload["data"] if payload["data"]["status"] == "COMPLETED" else None

    completed = wait_for("restart-safe reintegration completed", completed_reintegration, timeout=150)
    assert [stage["name"] for stage in completed["stages"]] == [
        "PROBING",
        "5%",
        "20%",
        "50%",
        "100%",
        "HEALTHY",
    ]
    assert all(stage["status"] == "VERIFIED" for stage in completed["stages"])
    _, final_actions = client.request("GET", f"/api/v1/environments/{ENVIRONMENT_ID}/actions")
    assert len([item for item in final_actions["data"]["items"] if item["incident_id"] == incident["id"]]) == 1
    _, final_incident = client.request("GET", f"/api/v1/incidents/{incident['id']}")
    assert final_incident["data"]["status"] == "RESOLVED"
    print("PASS: worker restart reconstructed recovery without replay or duplicate mutation")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
