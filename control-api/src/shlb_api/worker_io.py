from __future__ import annotations

import csv
import hashlib
import io
import json
import socket
from pathlib import Path

import httpx

from shlb_api.worker_policy import INSTANCES, ROUTES


class HAProxyRuntimeError(RuntimeError):
    pass


class HAProxyRuntime:
    def __init__(self, path: str = "/var/run/haproxy/haproxy.sock", timeout: float = 2.0):
        self.path = path
        self.timeout = timeout

    def command(self, value: str) -> str:
        if "\n" in value or len(value) > 512:
            raise ValueError("HAProxy Runtime command is malformed")
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(self.timeout)
        try:
            client.connect(self.path)
            client.sendall((value + "\n").encode("ascii"))
            client.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8", errors="replace")
        except OSError as exc:
            raise HAProxyRuntimeError(str(exc)) from exc
        finally:
            client.close()

    def info(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in self.command("show info").splitlines():
            key, separator, value = line.partition(":")
            if separator:
                result[key.strip()] = value.strip()
        return result

    def memberships(self) -> list[dict]:
        raw = self.command("show stat")
        reader = csv.DictReader(io.StringIO(raw.lstrip("# ")))
        rows: list[dict] = []
        for row in reader:
            backend = (row.get("pxname") or "").strip()
            server = (row.get("svname") or "").strip()
            if not backend.startswith("be_") or server in {"BACKEND", "FRONTEND", ""}:
                continue
            status = (row.get("status") or "UNKNOWN").upper()
            admin_state = "drain" if status.startswith("DRAIN") else "maint" if status.startswith("MAINT") else "ready" if status.startswith("UP") else "down"
            rows.append({
                "backend": backend,
                "server": server,
                "admin_state": admin_state,
                "status": status,
                "weight": int(row.get("weight") or 0),
                "queue": int(row.get("qcur") or 0),
                "sessions": int(row.get("scur") or 0),
                "last_change_seconds": int(row.get("lastchg") or 0),
            })
        return rows

    def read(self, backend: str, server: str) -> dict:
        for item in self.memberships():
            if item["backend"] == backend and item["server"] == server:
                return item
        raise HAProxyRuntimeError(f"runtime target missing: {backend}/{server}")

    def set_absolute(self, backend: str, server: str, *, admin_state: str, weight: int) -> dict:
        if not backend.startswith("be_") or not server.startswith("srv_inst_") or admin_state not in {"ready", "drain"} or not 0 <= weight <= 256:
            raise ValueError("requested Runtime state is outside the predeclared LAB mapping")
        target = f"{backend}/{server}"
        if admin_state == "drain":
            commands = [f"set server {target} weight {weight}", f"set server {target} state drain"]
        else:
            commands = [f"set server {target} weight {weight}", f"set server {target} state ready"]
        responses = []
        for command in commands:
            output = self.command(command)
            if output.strip():
                raise HAProxyRuntimeError(output.strip())
            responses.append({"command_hash": hashlib.sha256(command.encode()).hexdigest(), "accepted": True})
        return {"commands": responses, "observed": self.read(backend, server)}


class PrometheusEvidence:
    def __init__(self, base_url: str = "http://prometheus:9090"):
        self.client = httpx.Client(base_url=base_url, timeout=httpx.Timeout(2.0, connect=1.0))

    def query(self, expression: str) -> list[dict]:
        response = self.client.get("/api/v1/query", params={"query": expression})
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            raise RuntimeError("Prometheus query was not successful")
        return payload["data"]["result"]

    def collect(self, window: str = "12s") -> dict[str, dict]:
        evidence = {f"{route}/{instance}": {"samples": 0, "errors": 0, "error_rate": None, "p95_ms": None} for route in ROUTES for instance in INSTANCES}
        rows = self.query(f"sum by (instance,route,status_family) (increase(shlb_backend_requests_total[{window}]))")
        for row in rows:
            metric = row.get("metric", {})
            key = f"{metric.get('route')}/{metric.get('instance')}"
            if key not in evidence:
                continue
            value = max(0, int(round(float(row["value"][1]))))
            evidence[key]["samples"] += value
            if metric.get("status_family") == "5xx":
                evidence[key]["errors"] += value
        p95_rows = self.query(f"histogram_quantile(0.95, sum by (le,instance,route) (rate(shlb_backend_request_duration_seconds_bucket[{window}])))")
        p95 = {f"{row.get('metric', {}).get('route')}/{row.get('metric', {}).get('instance')}": float(row["value"][1]) for row in p95_rows}
        for key, member in evidence.items():
            samples = member["samples"]
            member["error_rate"] = round(member["errors"] / samples, 4) if samples else None
            member["p95_ms"] = round(p95[key] * 1000, 2) if samples and key in p95 else None
        return evidence


class LabProbeClient:
    def __init__(self, token_path: str = "/run/secrets/fault_control_token"):
        token = Path(token_path).read_text(encoding="utf-8").strip()
        if len(token) < 24:
            raise RuntimeError("LAB fault token is unavailable")
        self.headers = {"X-SHLB-Lab-Token": token}
        self.client = httpx.Client(timeout=httpx.Timeout(1.5, connect=0.75), headers=self.headers)

    @staticmethod
    def host(instance: str) -> str:
        if instance not in INSTANCES:
            raise ValueError("unregistered LAB instance")
        return f"http://demo-backend-{instance[-1]}:8080"

    def probes(self) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for route in ROUTES:
            for instance in INSTANCES:
                key = f"{route}/{instance}"
                try:
                    response = self.client.get(f"{self.host(instance)}/__lab/probe/{route}")
                    payload = response.json()
                    results[key] = {"reachable": True, "application_ok": response.status_code == 200 and payload.get("application_ok") is True, "status": response.status_code}
                except (httpx.HTTPError, json.JSONDecodeError):
                    results[key] = {"reachable": False, "application_ok": False, "status": None}
        return results

    def apply_fault(self, instance: str, payload: dict) -> dict:
        response = self.client.put(f"{self.host(instance)}/__lab/fault", json=payload)
        response.raise_for_status()
        return response.json()

    def clear_fault(self, instance: str) -> dict:
        response = self.client.delete(f"{self.host(instance)}/__lab/fault")
        response.raise_for_status()
        return response.json()
