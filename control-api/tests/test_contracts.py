from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from shlb_api.schemas import BackendCreate, FailureClass, FingerprintContract
from shlb_api.settings import Settings


def test_failure_taxonomy_is_frozen_to_eight_classes() -> None:
    assert [item.value for item in FailureClass] == [
        "HEALTHY",
        "INSTANCE_DOWN",
        "INSTANCE_DEGRADED",
        "ROUTE_INSTANCE_FAILURE",
        "SHARED_ROUTE_FAILURE",
        "TRAFFIC_OVERLOAD",
        "VERSION_SPECIFIC_FAILURE",
        "UNKNOWN",
    ]


def test_fingerprint_contract_bounds_completeness() -> None:
    now = datetime.now(UTC)
    valid = FingerprintContract(
        schema_version="fingerprint-v1",
        window_start=now - timedelta(seconds=30),
        window_end=now,
        affected_route_ids=[],
        affected_instance_ids=[],
        affected_version_ids=[],
        source_freshness_seconds={"haproxy": 2.0},
        sample_counts={"requests": 20},
        completeness=0.8,
        conflicts=[],
    )
    assert valid.completeness == 0.8
    with pytest.raises(ValidationError):
        FingerprintContract.model_validate({**valid.model_dump(), "completeness": 1.1})


@pytest.mark.parametrize(
    "address",
    [
        "http://backend.local",
        "127.0.0.1",
        "169.254.1.1",
        "user:password@backend.local",
    ],
)
def test_backend_registry_rejects_unsafe_address_forms(address: str) -> None:
    with pytest.raises(ValidationError):
        BackendCreate(
            service_id="50000000-0000-4000-8000-000000000001",
            stable_name="unsafe",
            address=address,
            port=8080,
            capacity=100,
            probe_profile="healthz",
        )


def test_backend_registry_accepts_bounded_private_dns_name() -> None:
    model = BackendCreate(
        service_id="50000000-0000-4000-8000-000000000001",
        stable_name="backend-d",
        address="demo-backend-d",
        port=8080,
        capacity=100,
        probe_profile="healthz",
    )
    assert model.address == "demo-backend-d"


def test_settings_fail_closed_on_missing_or_short_secrets(tmp_path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(RuntimeError, match="unavailable"):
        Settings(database_password_file=missing).database_password

    short = tmp_path / "short"
    short.write_text("too-short", encoding="utf-8")
    with pytest.raises(RuntimeError, match="minimum length"):
        Settings(database_password_file=short).database_password


def test_field_encryption_key_requires_exactly_32_bytes(tmp_path) -> None:
    key_file = tmp_path / "field-key"
    key_file.write_text(
        base64.urlsafe_b64encode(b"a" * 31).decode("ascii"),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="exactly 32 bytes"):
        Settings(field_encryption_key_file=key_file).field_encryption_key
