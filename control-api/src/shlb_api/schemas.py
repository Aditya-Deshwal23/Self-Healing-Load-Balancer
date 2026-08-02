from __future__ import annotations

import ipaddress
import re
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]


class FailureClass(StrEnum):
    HEALTHY = "HEALTHY"
    INSTANCE_DOWN = "INSTANCE_DOWN"
    INSTANCE_DEGRADED = "INSTANCE_DEGRADED"
    ROUTE_INSTANCE_FAILURE = "ROUTE_INSTANCE_FAILURE"
    SHARED_ROUTE_FAILURE = "SHARED_ROUTE_FAILURE"
    TRAFFIC_OVERLOAD = "TRAFFIC_OVERLOAD"
    VERSION_SPECIFIC_FAILURE = "VERSION_SPECIFIC_FAILURE"
    UNKNOWN = "UNKNOWN"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("must be a valid email address")
        return normalized


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: uuid.UUID
    name: str = Field(min_length=3, max_length=160)
    slug: Slug


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=3, max_length=160)
    status: str | None = Field(default=None, pattern=r"^(ACTIVE|ARCHIVED)$")


class EnvironmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    kind: str = Field(pattern=r"^(DEV|LAB|DEMO|PILOT)$")
    mode: str = Field(default="OBSERVE_ONLY", pattern=r"^(OBSERVE_ONLY|RULES_ONLY|MANUAL|SAFE_MODE)$")
    timezone: str = Field(default="UTC", min_length=1, max_length=64)


class EnvironmentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    mode: str | None = Field(
        default=None,
        pattern=r"^(OBSERVE_ONLY|RULES_ONLY|MANUAL|SAFE_MODE)$",
    )
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    automation_frozen: bool | None = None


class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    protocol: str = Field(default="HTTP", pattern=r"^(HTTP|HTTPS|TCP)$")


class VersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_label: str = Field(min_length=1, max_length=120)
    artifact_digest: str = Field(min_length=8, max_length=160)
    deployed_at: datetime | None = None


class BackendCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: uuid.UUID
    stable_name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    address: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)
    version_id: uuid.UUID | None = None
    capacity: int = Field(gt=0, le=1_000_000)
    probe_profile: str = Field(min_length=1, max_length=80)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        address = value.strip().lower()
        if any(character in address for character in "/:@?#[]"):
            raise ValueError("must be a host or IP address without a URL, port, or credentials")
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            if not re.fullmatch(
                r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?",
                address,
            ):
                raise ValueError("must be a bounded DNS name or IP address") from None
        else:
            if parsed.is_loopback or parsed.is_link_local or parsed.is_multicast or parsed.is_unspecified:
                raise ValueError("loopback, link-local, multicast, and unspecified addresses are forbidden")
        return address


class BackendPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: uuid.UUID | None = None
    capacity: int | None = Field(default=None, gt=0, le=1_000_000)
    probe_profile: str | None = Field(default=None, min_length=1, max_length=80)
    status: str | None = Field(default=None, pattern=r"^(ACTIVE|MAINTENANCE|ARCHIVED)$")


class RouteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    match_type: str = Field(pattern=r"^(EXACT|PREFIX|TEMPLATE)$")
    match_value: str = Field(min_length=1, max_length=240)
    priority: int = Field(ge=0)
    criticality: str = Field(pattern=r"^(STANDARD|HIGH|CRITICAL)$")
    default_behavior: str = Field(default="FAIL_CLOSED", min_length=1, max_length=32)


class RoutePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int | None = Field(default=None, ge=0)
    criticality: str | None = Field(default=None, pattern=r"^(STANDARD|HIGH|CRITICAL)$")
    default_behavior: str | None = Field(default=None, min_length=1, max_length=32)


class MembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: uuid.UUID
    haproxy_backend: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    haproxy_server: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    baseline_weight: int = Field(default=100, ge=0, le=256)
    baseline_maxconn: int | None = Field(default=None, gt=0)


class MembershipPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_weight: int | None = Field(default=None, ge=0, le=256)
    baseline_maxconn: int | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, pattern=r"^(ACTIVE|ARCHIVED)$")


class RoutingPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_physical_reserve: int = Field(ge=0, le=100)
    maximum_simultaneous_quarantine: int = Field(ge=0, le=100)
    verification_settings: dict[str, Any] = Field(max_length=32)
    reintegration_settings: dict[str, Any] = Field(max_length=32)
    action_allowlist: list[str] = Field(min_length=1, max_length=16)


class RetryPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_category: str = Field(min_length=1, max_length=32)
    allowed_failures: list[str] = Field(max_length=32)
    maximum_cross_instance_retries: int = Field(ge=0, le=1)
    ambiguous_post_behavior: str = Field(min_length=1, max_length=32)


class LabFaultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str = Field(
        pattern=r"^(CHECKOUT_INST_B_FAILURE|INST_B_DOWN|SHARED_CHECKOUT_FAILURE|UNKNOWN_CONFLICT)$"
    )
    duration_seconds: int = Field(default=120, ge=5, le=600)


class FingerprintContract(BaseModel):
    """Versioned Phase-2 evidence contract; persistence is introduced in later evidence phases."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^fingerprint-v[1-9][0-9]*$")
    window_start: datetime
    window_end: datetime
    affected_route_ids: list[str] = Field(max_length=64)
    affected_instance_ids: list[str] = Field(max_length=64)
    affected_version_ids: list[str] = Field(max_length=64)
    source_freshness_seconds: dict[str, float] = Field(max_length=32)
    sample_counts: dict[str, int] = Field(max_length=64)
    completeness: float = Field(ge=0, le=1)
    conflicts: list[str] = Field(default_factory=list, max_length=32)


class ClassificationContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^classification-v[1-9][0-9]*$")
    final_class: FailureClass
    confidence: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    rules_version: str = Field(min_length=1, max_length=80)
    model_version: str | None = Field(default=None, max_length=80)
    alternatives: dict[FailureClass, float] = Field(default_factory=dict, max_length=8)
    reasons: list[str] = Field(min_length=1, max_length=32)


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    event_version: int = Field(ge=1)
    occurred_at: datetime
    published_at: datetime
    project_id: str
    environment_id: str | None = None
    service_id: str | None = None
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int = Field(ge=0)
    correlation_id: str
    incident_id: str | None = None
    action_id: str | None = None
    data: dict[str, Any]
