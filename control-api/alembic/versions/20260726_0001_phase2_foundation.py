"""Phase 2 identity, registry, policy, audit, outbox, and idempotency foundation.

Revision ID: 20260726_0001
Revises:
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def version() -> sa.Column:
    return sa.Column("version", sa.BigInteger(), server_default="1", nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("auth_version", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        version(),
        *timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE','LOCKED','DISABLED')", name="ck_users_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized"),
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        version(),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "team_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "role IN ('VIEWER','RESEARCHER','OPERATOR','APPROVER','PROJECT_ADMIN','SYSTEM_ADMIN')",
            name="ck_team_membership_role",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_membership"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        version(),
        *timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE','ARCHIVED','PURGE_PENDING')", name="ck_projects_status"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "slug", name="uq_project_team_slug"),
    )
    op.create_index("ix_projects_team_status", "projects", ["team_id", "status"])

    op.create_table(
        "environments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("automation_frozen", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("controller_generation", sa.BigInteger(), server_default="0", nullable=False),
        version(),
        *timestamps(),
        sa.CheckConstraint("kind IN ('DEV','LAB','DEMO','PILOT')", name="ck_environment_kind"),
        sa.CheckConstraint(
            "mode IN ('OBSERVE_ONLY','RULES_ONLY','MANUAL','SAFE_MODE')",
            name="ck_environment_mode",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_environment_project_name"),
    )
    op.create_index("ix_environments_project", "environments", ["project_id"])

    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        version(),
        *timestamps(),
        sa.CheckConstraint("protocol IN ('HTTP','HTTPS','TCP')", name="ck_service_protocol"),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("environment_id", "name", name="uq_service_environment_name"),
    )

    op.create_table(
        "deployment_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.String(length=120), nullable=False),
        sa.Column("artifact_digest", sa.String(length=160), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=24), nullable=False),
        version(),
        *timestamps(),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_id", "artifact_digest", name="uq_version_service_digest"),
        sa.UniqueConstraint("service_id", "version_label", name="uq_version_service_label"),
    )

    op.create_table(
        "backend_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid()),
        sa.Column("stable_name", sa.String(length=80), nullable=False),
        sa.Column("address_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("probe_profile", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        version(),
        *timestamps(),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name="ck_backend_port"),
        sa.CheckConstraint("capacity > 0 AND capacity <= 1000000", name="ck_backend_capacity"),
        sa.CheckConstraint("status IN ('ACTIVE','MAINTENANCE','ARCHIVED')", name="ck_backend_status"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["deployment_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_id", "stable_name", name="uq_backend_service_name"),
    )

    op.create_table(
        "route_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("route_key", sa.String(length=80), nullable=False),
        sa.Column("match_type", sa.String(length=16), nullable=False),
        sa.Column("match_value", sa.String(length=240), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("criticality", sa.String(length=16), nullable=False),
        sa.Column("default_behavior", sa.String(length=32), nullable=False),
        version(),
        *timestamps(),
        sa.CheckConstraint("match_type IN ('EXACT','PREFIX','TEMPLATE')", name="ck_route_match_type"),
        sa.CheckConstraint("criticality IN ('STANDARD','HIGH','CRITICAL')", name="ck_route_criticality"),
        sa.CheckConstraint("priority >= 0", name="ck_route_priority"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_id", "priority", name="uq_route_service_priority"),
        sa.UniqueConstraint("service_id", "route_key", name="uq_route_service_key"),
    )

    op.create_table(
        "route_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column("haproxy_backend", sa.String(length=80), nullable=False),
        sa.Column("haproxy_server", sa.String(length=80), nullable=False),
        sa.Column("baseline_weight", sa.Integer(), nullable=False),
        sa.Column("baseline_maxconn", sa.Integer()),
        sa.Column("status", sa.String(length=24), nullable=False),
        version(),
        *timestamps(),
        sa.CheckConstraint("baseline_weight BETWEEN 0 AND 256", name="ck_membership_weight"),
        sa.CheckConstraint("baseline_maxconn IS NULL OR baseline_maxconn > 0", name="ck_membership_maxconn"),
        sa.ForeignKeyConstraint(["instance_id"], ["backend_instances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["route_id"], ["route_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("haproxy_backend", "haproxy_server", name="uq_route_membership_haproxy"),
        sa.UniqueConstraint("route_id", "instance_id", name="uq_route_membership_pair"),
    )

    op.create_table(
        "routing_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("route_id", sa.Uuid()),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("minimum_physical_reserve", sa.Integer(), nullable=False),
        sa.Column("maximum_simultaneous_quarantine", sa.Integer(), nullable=False),
        sa.Column("verification_settings", sa.JSON(), nullable=False),
        sa.Column("reintegration_settings", sa.JSON(), nullable=False),
        sa.Column("action_allowlist", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "minimum_physical_reserve BETWEEN 0 AND 100",
            name="ck_routing_policy_reserve",
        ),
        sa.CheckConstraint("maximum_simultaneous_quarantine >= 0", name="ck_routing_policy_quarantine"),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["route_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("environment_id", "route_id", "revision", name="uq_routing_policy_revision"),
    )
    op.create_index(
        "uq_routing_policy_active_scope",
        "routing_policies",
        ["environment_id", "route_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )

    op.create_table(
        "retry_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("method_category", sa.String(length=32), nullable=False),
        sa.Column("allowed_failures", sa.JSON(), nullable=False),
        sa.Column("maximum_cross_instance_retries", sa.Integer(), nullable=False),
        sa.Column("ambiguous_post_behavior", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "maximum_cross_instance_retries BETWEEN 0 AND 1",
            name="ck_retry_policy_mvp_max",
        ),
        sa.ForeignKeyConstraint(["route_id"], ["route_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "revision", name="uq_retry_policy_revision"),
    )
    op.create_index(
        "uq_retry_policy_active_route",
        "retry_policies",
        ["route_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("environment_id", sa.Uuid()),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=120), nullable=False),
        sa.Column("before_hash", sa.String(length=64)),
        sa.Column("after_hash", sa.String(length=64)),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("prior_hash", sa.String(length=64)),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "sequence", name="uq_audit_project_sequence"),
    )
    op.create_index("ix_audit_project_created", "audit_events", ["project_id", "created_at"])

    op.create_table(
        "event_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("environment_id", sa.Uuid()),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", sa.String(length=120), nullable=False),
        sa.Column("aggregate_version", sa.BigInteger(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_outbox_unpublished", "event_outbox", ["published_at", "created_at"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=160), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("resource_id", sa.String(length=120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_user_id", "scope", "key_hash", name="uq_idempotency_actor_scope_key"),
    )
    op.create_index("ix_idempotency_expiry", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_expiry", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_event_outbox_unpublished", table_name="event_outbox")
    op.drop_table("event_outbox")
    op.drop_index("ix_audit_project_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("uq_retry_policy_active_route", table_name="retry_policies")
    op.drop_table("retry_policies")
    op.drop_index("uq_routing_policy_active_scope", table_name="routing_policies")
    op.drop_table("routing_policies")
    op.drop_table("route_memberships")
    op.drop_table("route_groups")
    op.drop_table("backend_instances")
    op.drop_table("deployment_versions")
    op.drop_table("services")
    op.drop_index("ix_environments_project", table_name="environments")
    op.drop_table("environments")
    op.drop_index("ix_projects_team_status", table_name="projects")
    op.drop_table("projects")
    op.drop_table("team_memberships")
    op.drop_table("teams")
    op.drop_table("users")
