from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import httpx

from shlb_api.worker_policy import INSTANCES, ROUTES


class HAProxyRuntimeError(RuntimeError):
    pass


class HAProxyRuntime:
    def __init__(self, path: str = "/var/run/haproxy/admin.sock", timeout: float = 0.15):
        self.path = path
        self.timeout = min(timeout, 0.15)
        self._previous_5xx: dict[str, int] = {}

    def command(self, value: str) -> str:
        if "\n" in value or len(value) > 512:
            raise ValueError("HAProxy Runtime command is malformed")
        try:
            return asyncio.run(self.async_command(value))
        except (OSError, asyncio.TimeoutError) as exc:
            detail = "Runtime socket timeout" if isinstance(exc, asyncio.TimeoutError) else str(exc)
            raise HAProxyRuntimeError(detail) from exc

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(self.path),
            timeout=self.timeout,
        )
        try:
            yield reader, writer
        finally:
            writer.close()
            await writer.wait_closed()

    async def async_command(self, value: str) -> str:
        if "\n" in value or len(value) > 512:
            raise ValueError("HAProxy Runtime command is malformed")
        deadline = asyncio.get_running_loop().time() + self.timeout
        try:
            async with self._connection() as (reader, writer):
                writer.write((value + "\n").encode("ascii"))
                await asyncio.wait_for(writer.drain(), timeout=max(0, deadline - asyncio.get_running_loop().time()))
                chunks: list[bytes] = []
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    chunk = await asyncio.wait_for(reader.read(65536), timeout=remaining)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", errors="replace")
        except (OSError, asyncio.TimeoutError) as exc:
            detail = "Runtime socket timeout" if isinstance(exc, asyncio.TimeoutError) else str(exc)
            raise HAProxyRuntimeError(detail) from exc

    def info(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in self.command("show info").splitlines():
            key, separator, value = line.partition(":")
            if separator:
                result[key.strip()] = value.strip()
        return result

    def memberships(self) -> list[dict]:
        raw = self.command("show stat")
        return self._parse_memberships(raw)

    @staticmethod
    def _rows(raw: str) -> list[dict[str, str]]:
        header = next((line[1:].strip() for line in raw.splitlines() if line.startswith("#")), None)
        if not header:
            return []
        return list(csv.DictReader(io.StringIO(header + "\n" + "\n".join(
            line for line in raw.splitlines() if line and not line.startswith("#")
        ))))

    @classmethod
    def _parse_memberships(cls, raw: str) -> list[dict]:
        rows: list[dict] = []
        for row in cls._rows(raw):
            backend = (row.get("pxname") or "").strip()
            server = (row.get("svname") or "").strip()
            if not backend.startswith("be_") or server in {"BACKEND", "FRONTEND", ""}:
                continue
            status = (row.get("status") or "UNKNOWN").upper()
            admin_state = "drain" if status.startswith("DRAIN") else "maint" if status.startswith("MAINT") else "ready" if status.startswith("UP") else "down"
            weight = cls._number(row.get("weight"), int)
            queue = cls._number(row.get("qcur"), int)
            sessions = cls._number(row.get("scur"), int)
            rows.append({
                "backend": backend,
                "server": server,
                "admin_state": admin_state,
                "status": status,
                "weight": weight if weight is not None else 0,
                "queue": queue if queue is not None else 0,
                "sessions": sessions if sessions is not None else 0,
                "last_change_seconds": cls._number(row.get("lastchg"), int) or 0,
            })
        return rows

    @staticmethod
    def _number(value: str | None, kind: type[int] | type[float]) -> int | float | None:
        if value is None or value.strip() == "-":
            return None
        try:
            return kind(value)
        except (TypeError, ValueError):
            return None

    def read(self, backend: str, server: str) -> dict:
        for item in self.memberships():
            if item["backend"] == backend and item["server"] == server:
                return item
        raise HAProxyRuntimeError(f"runtime target missing: {backend}/{server}")

    def fast_samples(self) -> dict[str, dict]:
        """Read instantaneous HAProxy response/error counters without ELK."""
        raw = self.command("show stat")
        return self._parse_fast_samples(raw)

    def _parse_fast_samples(self, raw: str) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for row in self._rows(raw):
            backend = (row.get("pxname") or "").strip()
            server = (row.get("svname") or "").strip()
            if not backend.startswith("be_") or server in {"BACKEND", "FRONTEND", ""}:
                continue
            key = f"{backend.removeprefix('be_')}/{server.removeprefix('srv_').replace('_', '-')}"
            errors = self._number(row.get("hrsp_5xx"), int)
            sample = {
                "latency_ms": self._number(row.get("rtime"), float),
                "errors_5xx": errors,
                "sessions": self._number(row.get("scur"), int),
                "queue": self._number(row.get("qcur"), int),
                "weight": self._number(row.get("weight"), int),
            }
            previous = self._previous_5xx.get(key)
            if errors is not None and previous is not None:
                delta = errors - previous
                if delta >= 0:
                    sample["errors_5xx_delta"] = delta
                else:
                    sample["counter_reset"] = True
            self._previous_5xx[key] = errors if errors is not None else previous
            result[key] = sample
        return result

    async def fast_samples_async(self) -> dict[str, dict]:
        """Read one complete Runtime response without blocking the event loop."""
        raw = await self.async_command("show stat")
        return self._parse_fast_samples(raw)

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
