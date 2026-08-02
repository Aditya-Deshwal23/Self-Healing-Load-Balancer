from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class VersionMixin:
    version: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1", nullable=False)


class User(Base, TimestampMixin, VersionMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email_normalized: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", nullable=False)
    auth_version: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("status IN ('ACTIVE','LOCKED','DISABLED')", name="ck_users_status"),)


class Team(Base, TimestampMixin, VersionMixin):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class TeamMembership(Base, TimestampMixin):
    __tablename__ = "team_memberships"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_membership"),
        CheckConstraint(
            "role IN ('VIEWER','RESEARCHER','OPERATOR','APPROVER','PROJECT_ADMIN','SYSTEM_ADMIN')",
            name="ck_team_membership_role",
        ),
    )


class Project(Base, TimestampMixin, VersionMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "slug", name="uq_project_team_slug"),
        CheckConstraint("status IN ('ACTIVE','ARCHIVED','PURGE_PENDING')", name="ck_projects_status"),
        Index("ix_projects_team_status", "team_id", "status"),
    )


class Environment(Base, TimestampMixin, VersionMixin):
    __tablename__ = "environments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    automation_frozen: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    controller_generation: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_environment_project_name"),
        CheckConstraint("kind IN ('DEV','LAB','DEMO','PILOT')", name="ck_environment_kind"),
        CheckConstraint(
            "mode IN ('OBSERVE_ONLY','RULES_ONLY','MANUAL','SAFE_MODE')",
            name="ck_environment_mode",
        ),
        Index("ix_environments_project", "project_id"),
    )


class Service(Base, TimestampMixin, VersionMixin):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), default="HTTP", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", nullable=False)

    __table_args__ = (
        UniqueConstraint("environment_id", "name", name="uq_service_environment_name"),
        CheckConstraint("protocol IN ('HTTP','HTTPS','TCP')", name="ck_service_protocol"),
    )


class DeploymentVersion(Base, TimestampMixin, VersionMixin):
    __tablename__ = "deployment_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    version_label: Mapped[str] = mapped_column(String(120), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(160), nullable=False)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", nullable=False)

    __table_args__ = (
        UniqueConstraint("service_id", "version_label", name="uq_version_service_label"),
        UniqueConstraint("service_id", "artifact_digest", name="uq_version_service_digest"),
    )


class BackendInstance(Base, TimestampMixin, VersionMixin):
    __tablename__ = "backend_instances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deployment_versions.id", ondelete="SET NULL"),
    )
    stable_name: Mapped[str] = mapped_column(String(80), nullable=False)
    address_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    probe_profile: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", nullable=False)

    __table_args__ = (
        UniqueConstraint("service_id", "stable_name", name="uq_backend_service_name"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="ck_backend_port"),
        CheckConstraint("capacity > 0 AND capacity <= 1000000", name="ck_backend_capacity"),
        CheckConstraint("status IN ('ACTIVE','MAINTENANCE','ARCHIVED')", name="ck_backend_status"),
    )


class RouteGroup(Base, TimestampMixin, VersionMixin):
    __tablename__ = "route_groups"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    route_key: Mapped[str] = mapped_column(String(80), nullable=False)
    match_type: Mapped[str] = mapped_column(String(16), nullable=False)
    match_value: Mapped[str] = mapped_column(String(240), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    criticality: Mapped[str] = mapped_column(String(16), nullable=False)
    default_behavior: Mapped[str] = mapped_column(String(32), default="FAIL_CLOSED", nullable=False)

    __table_args__ = (
        UniqueConstraint("service_id", "route_key", name="uq_route_service_key"),
        UniqueConstraint("service_id", "priority", name="uq_route_service_priority"),
        CheckConstraint("match_type IN ('EXACT','PREFIX','TEMPLATE')", name="ck_route_match_type"),
        CheckConstraint("criticality IN ('STANDARD','HIGH','CRITICAL')", name="ck_route_criticality"),
        CheckConstraint("priority >= 0", name="ck_route_priority"),
    )


class RouteMembership(Base, TimestampMixin, VersionMixin):
    __tablename__ = "route_memberships"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("route_groups.id", ondelete="CASCADE"), nullable=False)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backend_instances.id", ondelete="RESTRICT"),
        nullable=False,
    )
    haproxy_backend: Mapped[str] = mapped_column(String(80), nullable=False)
    haproxy_server: Mapped[str] = mapped_column(String(80), nullable=False)
    baseline_weight: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    baseline_maxconn: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", nullable=False)

    __table_args__ = (
        UniqueConstraint("route_id", "instance_id", name="uq_route_membership_pair"),
        UniqueConstraint("haproxy_backend", "haproxy_server", name="uq_route_membership_haproxy"),
        CheckConstraint("baseline_weight BETWEEN 0 AND 256", name="ck_membership_weight"),
        CheckConstraint("baseline_maxconn IS NULL OR baseline_maxconn > 0", name="ck_membership_maxconn"),
    )


class RoutingPolicy(Base, TimestampMixin):
    __tablename__ = "routing_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("route_groups.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    minimum_physical_reserve: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_simultaneous_quarantine: Mapped[int] = mapped_column(Integer, nullable=False)
    verification_settings: Mapped[dict] = mapped_column(JSON, nullable=False)
    reintegration_settings: Mapped[dict] = mapped_column(JSON, nullable=False)
    action_allowlist: Mapped[list] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    __table_args__ = (
        UniqueConstraint("environment_id", "route_id", "revision", name="uq_routing_policy_revision"),
        CheckConstraint(
            "minimum_physical_reserve BETWEEN 0 AND 100",
            name="ck_routing_policy_reserve",
        ),
        CheckConstraint("maximum_simultaneous_quarantine >= 0", name="ck_routing_policy_quarantine"),
        Index(
            "uq_routing_policy_active_scope",
            "environment_id",
            "route_id",
            unique=True,
            postgresql_where=active.is_(True),
        ),
    )


class RetryPolicy(Base, TimestampMixin):
    __tablename__ = "retry_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("route_groups.id", ondelete="CASCADE"), nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method_category: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed_failures: Mapped[list] = mapped_column(JSON, nullable=False)
    maximum_cross_instance_retries: Mapped[int] = mapped_column(Integer, nullable=False)
    ambiguous_post_behavior: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    __table_args__ = (
        UniqueConstraint("route_id", "revision", name="uq_retry_policy_revision"),
        CheckConstraint(
            "maximum_cross_instance_retries BETWEEN 0 AND 1",
            name="ck_retry_policy_mvp_max",
        ),
        Index(
            "uq_retry_policy_active_route",
            "route_id",
            unique=True,
            postgresql_where=active.is_(True),
        ),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="RESTRICT"),
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(120), nullable=False)
    before_hash: Mapped[str | None] = mapped_column(String(64))
    after_hash: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prior_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_audit_project_sequence"),
        Index("ix_audit_project_created", "project_id", "created_at"),
    )


class EventOutbox(Base):
    __tablename__ = "event_outbox"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_event_outbox_unpublished", "published_at", "created_at"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(160), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("actor_user_id", "scope", "key_hash", name="uq_idempotency_actor_scope_key"),
        Index("ix_idempotency_expiry", "expires_at"),
    )


class Incident(Base, TimestampMixin, VersionMixin):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    route_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("route_groups.id", ondelete="RESTRICT"))
    instance_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("backend_instances.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    operational_class: Mapped[str] = mapped_column(String(48), nullable=False)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('OPEN','MITIGATING','VERIFYING','RECOVERING','NEEDS_REVIEW','RESOLVED')", name="ck_incident_status"),
        CheckConstraint("severity IN ('INFO','WARNING','CRITICAL')", name="ck_incident_severity"),
        Index("ix_incidents_environment_status", "environment_id", "status", "opened_at"),
    )


class ObservationWindow(Base, TimestampMixin):
    __tablename__ = "observation_windows"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completeness: Mapped[float] = mapped_column(Float, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    probes: Mapped[dict] = mapped_column(JSON, nullable=False)
    freshness: Mapped[dict] = mapped_column(JSON, nullable=False)
    conflicts: Mapped[list] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        CheckConstraint("completeness >= 0 AND completeness <= 1", name="ck_observation_completeness"),
        Index("ix_observation_environment_end", "environment_id", "ended_at"),
    )


class Fingerprint(Base, TimestampMixin):
    __tablename__ = "fingerprints"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(24), nullable=False)
    canonical_value: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("ix_fingerprints_incident", "incident_id", "created_at"),)


class Classification(Base, TimestampMixin):
    __tablename__ = "classifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    observation_window_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("observation_windows.id", ondelete="RESTRICT"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    final_class: Mapped[str] = mapped_column(String(48), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_support: Mapped[dict] = mapped_column(JSON, nullable=False)
    competing_hypotheses: Mapped[list] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("incident_id", "revision", name="uq_classification_incident_revision"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_classification_confidence"),
        CheckConstraint("completeness >= 0 AND completeness <= 1", name="ck_classification_completeness"),
    )


class EvidenceCertificate(Base, TimestampMixin):
    __tablename__ = "evidence_certificates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    observation_window_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("observation_windows.id", ondelete="RESTRICT"), nullable=False)
    fingerprint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fingerprints.id", ondelete="RESTRICT"), nullable=False)
    classification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classifications.id", ondelete="RESTRICT"), nullable=False)
    certificate_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scope_evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    safety_inputs: Mapped[dict] = mapped_column(JSON, nullable=False)
    candidate_actions: Mapped[list] = mapped_column(JSON, nullable=False)


class DesiredRouteState(Base, TimestampMixin, VersionMixin):
    __tablename__ = "desired_route_states"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("route_memberships.id", ondelete="CASCADE"), nullable=False)
    admin_state: Mapped[str] = mapped_column(String(24), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    controller_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_action_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    __table_args__ = (
        UniqueConstraint("membership_id", name="uq_desired_route_membership"),
        CheckConstraint("weight BETWEEN 0 AND 256", name="ck_desired_route_weight"),
    )


class Action(Base, TimestampMixin, VersionMixin):
    __tablename__ = "actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False)
    evidence_certificate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence_certificates.id", ondelete="RESTRICT"), nullable=False)
    membership_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("route_memberships.id", ondelete="RESTRICT"), nullable=False)
    action_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    controller_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    haproxy_backend: Mapped[str] = mapped_column(String(80), nullable=False)
    haproxy_server: Mapped[str] = mapped_column(String(80), nullable=False)
    previous_desired: Mapped[dict] = mapped_column(JSON, nullable=False)
    previous_observed: Mapped[dict] = mapped_column(JSON, nullable=False)
    requested_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    expected_effect: Mapped[str] = mapped_column(String(500), nullable=False)
    preservation_set: Mapped[list] = mapped_column(JSON, nullable=False)
    verification_criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    rollback_strategy: Mapped[dict] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_actions_environment_lifecycle", "environment_id", "lifecycle", "created_at"),)


class ActionAttempt(Base, TimestampMixin):
    __tablename__ = "action_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actions.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    command_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    observed_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (UniqueConstraint("action_id", "sequence", name="uq_action_attempt_sequence"),)


class ObservedStateSnapshot(Base, TimestampMixin):
    __tablename__ = "observed_state_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    action_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("actions.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    process_id: Mapped[str | None] = mapped_column(String(80))
    config_identifier: Mapped[str | None] = mapped_column(String(120))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    memberships: Mapped[list] = mapped_column(JSON, nullable=False)

    __table_args__ = (Index("ix_observed_environment_time", "environment_id", "observed_at"),)


class VerificationResult(Base, TimestampMixin):
    __tablename__ = "verification_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actions.id", ondelete="CASCADE"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    affected_obligation: Mapped[dict] = mapped_column(JSON, nullable=False)
    preservation_obligation: Mapped[dict] = mapped_column(JSON, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("action_id", "revision", name="uq_verification_action_revision"),)


class ReintegrationRun(Base, TimestampMixin, VersionMixin):
    __tablename__ = "reintegration_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False)
    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actions.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    last_verified_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_retries: Mapped[int] = mapped_column(Integer, nullable=False)
    next_transition_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_reintegration_environment_status", "environment_id", "status"),)


class ReintegrationStage(Base, TimestampMixin):
    __tablename__ = "reintegration_stages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reintegration_runs.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(24), nullable=False)
    requested_weight: Mapped[int | None] = mapped_column(Integer)
    observed_weight: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_reintegration_stage_sequence"),)


class LabFault(Base, TimestampMixin, VersionMixin):
    __tablename__ = "lab_faults"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    scenario: Mapped[str] = mapped_column(String(48), nullable=False)
    target_route: Mapped[str | None] = mapped_column(String(80))
    target_instance: Mapped[str | None] = mapped_column(String(80))
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    ground_truth_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("duration_seconds BETWEEN 5 AND 600", name="ck_lab_fault_duration"),
        Index("ix_lab_faults_environment_status", "environment_id", "status"),
    )


class ControllerGeneration(Base, TimestampMixin):
    __tablename__ = "controller_generations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("environment_id", "generation", name="uq_controller_environment_generation"),
        Index("ix_controller_environment_heartbeat", "environment_id", "last_heartbeat_at"),
    )
