#!/usr/bin/env python3
"""Prove that a Runtime weight change is scoped to one logical membership.

The test deliberately reads HAProxy's observed server state before and after the
command. It does not trust a controller response. The original weight is always
restored, including when an assertion fails.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROUTE_BACKENDS = ("be_public", "be_auth", "be_catalog", "be_checkout")
PHYSICAL_INSTANCE_MEMBER = "srv_inst_b"
TARGET_BACKEND = "be_checkout"

# Fields that describe address and administrative/operational routing state.
# Volatile check timestamps/results and traffic counters are intentionally not
# compared because they can change while this test is running.
STABLE_OBSERVED_FIELDS = (
    "be_name",
    "srv_name",
    "srv_addr",
    "srv_op_state",
    "srv_admin_state",
    "srv_uweight",
    "srv_iweight",
    "srv_check_state",
    "srv_agent_state",
    "srv_fqdn",
    "srv_port",
    "srvrecord",
)


class IsolationTestError(RuntimeError):
    """Raised when the lab state cannot establish membership isolation."""


@dataclass(frozen=True)
class RuntimeClient:
    compose_file: Path
    service: str
    socket_path: str

    def command(self, value: str) -> str:
        process = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
                "exec",
                "-T",
                self.service,
                "socat",
                "-",
                f"UNIX-CONNECT:{self.socket_path}",
            ],
            input=value.rstrip("\n") + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            detail = process.stderr.strip() or process.stdout.strip() or "no output"
            raise IsolationTestError(f"Runtime command {value!r} failed: {detail}")
        return process.stdout


def parse_server_state(raw: str) -> dict[tuple[str, str], dict[str, str]]:
    """Parse `show servers state` without pinning a HAProxy column count."""
    header: list[str] | None = None
    rows: dict[tuple[str, str], dict[str, str]] = {}

    for unstripped in raw.splitlines():
        line = unstripped.strip()
        if not line:
            continue
        if line.startswith("#"):
            candidate = line.removeprefix("#").strip().split()
            if "be_name" in candidate and "srv_name" in candidate:
                header = candidate
            continue
        if header is None:
            continue

        values = line.split()
        if len(values) < len(header):
            # HAProxy uses '-' for empty fields, so a shorter row indicates an
            # incompatible/partial response rather than a legitimate blank.
            raise IsolationTestError(
                f"Runtime state row has {len(values)} values for {len(header)} columns: {line}"
            )
        row = dict(zip(header, values, strict=False))
        key = (row["be_name"], row["srv_name"])
        rows[key] = row

    if header is None:
        raise IsolationTestError("HAProxy Runtime response had no server-state header")
    return rows


def membership_rows(
    rows: dict[tuple[str, str], dict[str, str]],
) -> dict[str, dict[str, str]]:
    selected: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for backend in ROUTE_BACKENDS:
        row = rows.get((backend, PHYSICAL_INSTANCE_MEMBER))
        if row is None:
            missing.append(f"{backend}/{PHYSICAL_INSTANCE_MEMBER}")
        else:
            selected[backend] = row
    if missing:
        raise IsolationTestError(f"Missing logical memberships: {', '.join(missing)}")
    return selected


def stable_projection(row: dict[str, str]) -> dict[str, str]:
    required = {"be_name", "srv_name", "srv_op_state", "srv_admin_state", "srv_uweight"}
    absent = sorted(required.difference(row))
    if absent:
        raise IsolationTestError(f"Runtime state is missing required fields: {', '.join(absent)}")
    return {field: row[field] for field in STABLE_OBSERVED_FIELDS if field in row}


def observe(client: RuntimeClient) -> dict[str, dict[str, str]]:
    return membership_rows(parse_server_state(client.command("show servers state")))


def changed_fields(before: dict[str, str], after: dict[str, str]) -> dict[str, tuple[str, str]]:
    return {
        field: (before.get(field, "<absent>"), after.get(field, "<absent>"))
        for field in sorted(set(before) | set(after))
        if before.get(field) != after.get(field)
    }


def wait_for_weight(
    client: RuntimeClient,
    expected: int,
    *,
    timeout_seconds: float = 5.0,
) -> dict[str, dict[str, str]]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, dict[str, str]] | None = None
    while time.monotonic() < deadline:
        last = observe(client)
        if last[TARGET_BACKEND].get("srv_uweight") == str(expected):
            return last
        time.sleep(0.1)
    observed = None if last is None else last[TARGET_BACKEND].get("srv_uweight")
    raise IsolationTestError(
        f"Timed out waiting for {TARGET_BACKEND}/{PHYSICAL_INSTANCE_MEMBER} "
        f"weight {expected}; observed {observed}"
    )


def format_memberships(rows: dict[str, dict[str, str]]) -> Iterable[str]:
    for backend in ROUTE_BACKENDS:
        row = rows[backend]
        yield (
            f"  {backend}/{PHYSICAL_INSTANCE_MEMBER}: "
            f"op={row['srv_op_state']} admin={row['srv_admin_state']} "
            f"weight={row['srv_uweight']}/{row.get('srv_iweight', '?')}"
        )


def run_test(client: RuntimeClient, requested_weight: int) -> None:
    before = observe(client)
    target_before = stable_projection(before[TARGET_BACKEND])
    original_weight = int(target_before["srv_uweight"])
    test_weight = requested_weight if requested_weight != original_weight else requested_weight + 1

    before_controls = {
        backend: stable_projection(row)
        for backend, row in before.items()
        if backend != TARGET_BACKEND
    }

    print("Observed physical instance B memberships before change:")
    print("\n".join(format_memberships(before)))
    print(
        f"\nApplying Runtime weight {test_weight} only to "
        f"{TARGET_BACKEND}/{PHYSICAL_INSTANCE_MEMBER}"
    )

    changed_state: dict[str, dict[str, str]] | None = None
    test_error: BaseException | None = None
    try:
        response = client.command(
            f"set server {TARGET_BACKEND}/{PHYSICAL_INSTANCE_MEMBER} weight {test_weight}"
        )
        if response.strip():
            raise IsolationTestError(f"HAProxy rejected the Runtime mutation: {response.strip()}")

        changed_state = wait_for_weight(client, test_weight)
        target_after = stable_projection(changed_state[TARGET_BACKEND])
        target_delta = changed_fields(target_before, target_after)
        if target_delta.get("srv_uweight") != (str(original_weight), str(test_weight)):
            raise IsolationTestError(f"Target weight did not change as requested: {target_delta}")

        unexpected_target_changes = set(target_delta).difference({"srv_uweight"})
        if unexpected_target_changes:
            raise IsolationTestError(
                "Target mutation changed additional stable fields: "
                + ", ".join(sorted(unexpected_target_changes))
            )

        for backend, before_projection in before_controls.items():
            after_projection = stable_projection(changed_state[backend])
            delta = changed_fields(before_projection, after_projection)
            if delta:
                raise IsolationTestError(
                    f"Unaffected membership {backend}/{PHYSICAL_INSTANCE_MEMBER} changed: {delta}"
                )
    except BaseException as exc:  # restoration must run for assertions and interrupts
        test_error = exc
    finally:
        try:
            client.command(
                f"set server {TARGET_BACKEND}/{PHYSICAL_INSTANCE_MEMBER} weight {original_weight}"
            )
            restored = wait_for_weight(client, original_weight)
            restored_target = stable_projection(restored[TARGET_BACKEND])
            restore_delta = changed_fields(target_before, restored_target)
            if restore_delta:
                raise IsolationTestError(f"Target did not return to its original state: {restore_delta}")
        except BaseException as restore_error:
            if test_error is not None:
                raise IsolationTestError(
                    f"Isolation assertion failed ({test_error}); restoration also failed ({restore_error})"
                ) from restore_error
            raise

    if test_error is not None:
        raise test_error

    assert changed_state is not None
    print("\nObserved memberships during the scoped change:")
    print("\n".join(format_memberships(changed_state)))
    print(
        "\nPASS: checkout/backend-B changed independently; public/backend-B, "
        "auth/backend-B, and catalog/backend-B retained identical observed control state."
    )
    print(f"PASS: restored checkout/backend-B to weight {original_weight}.")


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compose-file",
        type=Path,
        default=repository / "docker-compose.yml",
        help="Compose file for the running Phase 1 lab",
    )
    parser.add_argument("--service", default="traffic-haproxy")
    parser.add_argument("--socket", default="/var/run/haproxy/haproxy.sock")
    parser.add_argument("--test-weight", type=int, default=37)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0 <= args.test_weight <= 256:
        print("ERROR: --test-weight must be between 0 and 256", file=sys.stderr)
        return 2

    client = RuntimeClient(
        compose_file=args.compose_file.resolve(),
        service=args.service,
        socket_path=args.socket,
    )
    try:
        run_test(client, args.test_weight)
    except (IsolationTestError, FileNotFoundError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

