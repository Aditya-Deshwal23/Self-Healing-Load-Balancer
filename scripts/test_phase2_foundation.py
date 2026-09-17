#!/usr/bin/env python3
from __future__ import annotations

import http.cookiejar
import json
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://localhost:8443"
PRIMARY_PROJECT = "30000000-0000-4000-8000-000000000001"
FOREIGN_PROJECT = "30000000-0000-4000-8000-000000000099"
PRIMARY_ENVIRONMENT = "40000000-0000-4000-8000-000000000001"
PRIMARY_SERVICE = "50000000-0000-4000-8000-000000000001"
CHECKOUT_ROUTE = "80000000-0000-4000-8000-000000000004"
TEAM_ID = "20000000-0000-4000-8000-000000000001"
ORIGIN = BASE_URL


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
        self.counter = 0

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected: int = 200,
    ) -> tuple[Any, Any]:
        self.counter += 1
        request_headers = {
            "Accept": "application/json",
            "X-Request-ID": f"phase2-test-{self.counter:04d}",
            **(headers or {}),
        }
        encoded = None
        if body is not None:
            encoded = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=encoded,
            headers=request_headers,
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=8)
            raw = response.read()
        except urllib.error.HTTPError as exc:
            response = exc
            raw = exc.read()
        if response.status != expected:
            safe_body = raw.decode("utf-8", errors="replace")[:1000]
            raise AssertionError(
                f"{method} {path}: expected {expected}, received {response.status}: {safe_body}"
            )
        parsed = json.loads(raw) if raw else None
        return response, parsed


def compose(*args: str) -> str:
    completed = subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def inspect_container(service: str) -> dict[str, Any]:
    container_id = compose("ps", "-q", service)
    if not container_id:
        raise AssertionError(f"{service} container is not running")
    completed = subprocess.run(
        ["docker", "inspect", container_id],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)[0]


def assert_runtime_boundaries() -> None:
    api = inspect_container("control-api")
    network_names = set(api["NetworkSettings"]["Networks"])
    assert any(name.endswith("_api_edge_net") for name in network_names)
    assert any(name.endswith("_control_data_net") for name in network_names)
    assert not any(name.endswith("_data_edge_net") for name in network_names)
    assert not any(name.endswith("_observability_net") for name in network_names)
    assert not any(name.endswith("_backend_net") for name in network_names)

    mounts = json.dumps(api["Mounts"]).lower()
    environment = "\n".join(api["Config"].get("Env") or []).lower()
    assert "haproxy" not in mounts
    assert "docker.sock" not in mounts
    assert "haproxy" not in environment
    assert api["HostConfig"]["ReadonlyRootfs"] is True
    assert not (api["NetworkSettings"]["Ports"].get("8000/tcp") or [])

    for service, port in (("postgres", "5432/tcp"), ("redis", "6379/tcp")):
        record = inspect_container(service)
        assert not (record["NetworkSettings"]["Ports"].get(port) or [])
        assert record["HostConfig"]["ReadonlyRootfs"] is True


def main() -> int:
    client = Client()
    response, problem = client.request(
        "GET",
        "/api/v1/system/status",
        expected=401,
    )
    assert response.headers.get_content_type() == "application/problem+json"
    assert problem["code"] == "UNAUTHENTICATED"
    assert response.headers["X-Request-ID"] == problem["request_id"]
    assert len(problem["request_id"]) >= 8

    _, invalid_login = client.request(
        "POST",
        "/api/v1/auth/login",
        body={"email": "missing-account@shlb.local", "password": "incorrect"},
        expected=401,
    )
    assert invalid_login["code"] == "INVALID_CREDENTIALS"
    assert "account" not in invalid_login["detail"].lower()

    bootstrap_password = (ROOT / ".secrets/bootstrap_password").read_text(
        encoding="utf-8"
    ).strip()
    response, login = client.request(
        "POST",
        "/api/v1/auth/login",
        body={"email": "admin@shlb.local", "password": bootstrap_password},
    )
    cookie_headers = response.headers.get_all("Set-Cookie") or []
    cookie_contract = "\n".join(cookie_headers).lower()
    assert "secure" in cookie_contract
    assert "httponly" in cookie_contract
    assert "samesite=strict" in cookie_contract
    csrf = login["data"]["csrf_token"]
    assert login["data"]["scopes"][0]["role"] == "PROJECT_ADMIN"

    _, status = client.request("GET", "/api/v1/system/status")
    control = status["data"]["control_plane"]
    assert control["haproxy_access"] is False
    assert control["control_authority"] == "API_EXCLUDED_WORKER_ONLY"
    assert control["worker"] == "READY"
    assert status["data"]["data_plane"]["observed_state"] == "CONFIRMED"

    _, capabilities = client.request("GET", "/api/v1/system/capabilities")
    assert capabilities["data"]["phase"] == "rules-only-prototype"
    assert capabilities["data"]["features"]["routing_mutations"] is True
    assert capabilities["data"]["failure_classes"] == [
        "HEALTHY",
        "INSTANCE_DOWN",
        "ROUTE_INSTANCE_FAILURE",
        "SHARED_ROUTE_FAILURE",
        "UNKNOWN",
    ]
    assert "HAProxy Runtime API" in capabilities["data"]["authority"]["api_process_excludes"]

    _, projects = client.request("GET", "/api/v1/projects?limit=1")
    assert len(projects["data"]) == 1
    assert projects["data"][0]["id"] == PRIMARY_PROJECT
    client.request("GET", f"/api/v1/projects/{FOREIGN_PROJECT}", expected=404)

    create_body = {
        "team_id": TEAM_ID,
        "name": "Phase 2 contract project",
        "slug": "phase-2-contract-project",
    }
    mutation_headers = {
        "X-CSRF-Token": csrf,
        "Origin": ORIGIN,
        "Idempotency-Key": "phase2-contract-project-v1",
    }
    first_response, first_create = client.request(
        "POST",
        "/api/v1/projects",
        body=create_body,
        headers=mutation_headers,
        expected=201,
    )
    replay_response, replay_create = client.request(
        "POST",
        "/api/v1/projects",
        body=create_body,
        headers=mutation_headers,
        expected=201,
    )
    assert first_create["data"]["id"] == replay_create["data"]["id"]
    assert replay_response.headers["Idempotent-Replay"] == "true"
    mismatch = {**create_body, "name": "Different canonical request"}
    client.request(
        "POST",
        "/api/v1/projects",
        body=mismatch,
        headers=mutation_headers,
        expected=409,
    )
    client.request(
        "POST",
        "/api/v1/projects",
        body={
            "team_id": "20000000-0000-4000-8000-000000000099",
            "name": "Cross-scope attempt",
            "slug": "cross-scope-attempt",
        },
        headers={
            "X-CSRF-Token": csrf,
            "Origin": ORIGIN,
            "Idempotency-Key": "phase2-cross-scope-attempt",
        },
        expected=403,
    )

    _, first_page = client.request("GET", "/api/v1/projects?limit=1")
    assert first_page["page"]["next_cursor"]
    encoded_cursor = urllib.parse.quote(
        first_page["page"]["next_cursor"],
        safe="",
    )
    _, second_page = client.request(
        "GET",
        f"/api/v1/projects?limit=1&cursor={encoded_cursor}",
    )
    assert second_page["data"][0]["id"] != first_page["data"][0]["id"]
    client.request(
        "GET",
        "/api/v1/projects?cursor=not-a-valid-cursor",
        expected=422,
    )

    client.request(
        "POST",
        f"/api/v1/projects/{PRIMARY_PROJECT}/environments",
        body={
            "name": "Missing CSRF fixture",
            "kind": "LAB",
            "mode": "OBSERVE_ONLY",
            "timezone": "UTC",
        },
        headers={
            "Origin": ORIGIN,
            "Idempotency-Key": "phase2-missing-csrf",
        },
        expected=403,
    )

    project_response, _ = client.request(
        "GET",
        f"/api/v1/projects/{PRIMARY_PROJECT}",
    )
    assert project_response.headers["ETag"] == '"1"'
    client.request(
        "PATCH",
        f"/api/v1/projects/{PRIMARY_PROJECT}",
        body={"name": "No entity version"},
        headers={"X-CSRF-Token": csrf, "Origin": ORIGIN},
        expected=428,
    )

    _, services = client.request(
        "GET",
        f"/api/v1/environments/{PRIMARY_ENVIRONMENT}/services",
    )
    assert [item["id"] for item in services["data"]] == [PRIMARY_SERVICE]
    _, backends = client.request(
        "GET",
        f"/api/v1/environments/{PRIMARY_ENVIRONMENT}/backends",
    )
    assert len(backends["data"]) == 3
    assert sum(item["capacity"] for item in backends["data"]) == 300
    assert all(item["endpoint"]["address"] == "encrypted" for item in backends["data"])

    _, routes = client.request("GET", f"/api/v1/services/{PRIMARY_SERVICE}/routes")
    assert len(routes["data"]) == 4
    _, memberships = client.request(
        "GET",
        f"/api/v1/routes/{CHECKOUT_ROUTE}/memberships",
    )
    assert len(memberships["data"]) == 3
    assert all(
        item["observed_state"]["status"] == "UNKNOWN"
        for item in memberships["data"]
    )

    openapi_response, openapi = client.request("GET", "/api/v1/openapi.json")
    assert openapi_response.status == 200
    for path in (
        "/api/v1/auth/login",
        "/api/v1/projects",
        "/api/v1/environments/{environment_id}/backends",
        "/api/v1/events",
    ):
        assert path in openapi["paths"]

    stream_request = urllib.request.Request(
        (
            f"{BASE_URL}/api/v1/events"
            f"?project_id={PRIMARY_PROJECT}&environment_id={PRIMARY_ENVIRONMENT}"
        ),
        headers={
            "Accept": "text/event-stream",
            "Last-Event-ID": "outside-retained-history",
        },
        method="GET",
    )
    stream_response = client.opener.open(stream_request, timeout=8)
    stream_lines = [
        stream_response.readline().decode("utf-8").strip()
        for _ in range(4)
    ]
    stream_response.close()
    assert stream_response.status == 200
    assert stream_response.headers.get_content_type() == "text/event-stream"
    assert stream_lines[1] == "event: resync_required"
    assert stream_lines[2].startswith("data: ")
    assert json.loads(stream_lines[2][6:])["event_type"] == "resync_required"

    session_cookie = next(
        cookie.value for cookie in client.cookies if cookie.name == "shlb_session"
    )
    ttl_output = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "redis",
            "sh",
            "-c",
            'REDISCLI_AUTH="$(cat /run/secrets/redis_password)" redis-cli TTL "$1"',
            "sh",
            f"sess:{session_cookie}",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    assert 0 < int(ttl_output) <= 8 * 60 * 60

    audit_count = int(
        compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "shlb_api",
            "-d",
            "shlb",
            "-Atc",
            "SELECT count(*) FROM audit_events",
        )
    )
    idempotency_count = int(
        compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "shlb_api",
            "-d",
            "shlb",
            "-Atc",
            "SELECT count(*) FROM idempotency_records",
        )
    )
    assert audit_count >= 2
    assert idempotency_count >= 1
    assert_runtime_boundaries()

    client.request(
        "POST",
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf, "Origin": ORIGIN},
    )
    client.request("GET", "/api/v1/auth/me", expected=401)
    print("Rules-only API, session, scope, idempotency, SSE, persistence, and isolation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
