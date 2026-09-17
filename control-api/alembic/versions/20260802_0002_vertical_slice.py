"""Durable rules-only incident, action, verification, reintegration, and LAB state.

Revision ID: 20260802_0002
Revises: 20260726_0001
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0002"
down_revision: str | None = "20260726_0001"
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
        "incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("route_id", sa.Uuid()),
        sa.Column("instance_id", sa.Uuid()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("operational_class", sa.String(48), nullable=False),
        sa.Column("fingerprint_hash", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        version(), *timestamps(),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["route_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["instance_id"], ["backend_instances.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('OPEN','MITIGATING','VERIFYING','RECOVERING','NEEDS_REVIEW','RESOLVED')", name="ck_incident_status"),
        sa.CheckConstraint("severity IN ('INFO','WARNING','CRITICAL')", name="ck_incident_severity"),
    )
    op.create_index("ix_incidents_environment_status", "incidents", ["environment_id", "status", "opened_at"])

    op.create_table(
        "observation_windows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completeness", sa.Float(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("probes", sa.JSON(), nullable=False),
        sa.Column("freshness", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.CheckConstraint("completeness >= 0 AND completeness <= 1", name="ck_observation_completeness"),
    )
    op.create_index("ix_observation_environment_end", "observation_windows", ["environment_id", "ended_at"])

    op.create_table(
        "fingerprints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(24), nullable=False),
        sa.Column("canonical_value", sa.Text(), nullable=False),
        sa.Column("fingerprint_hash", sa.String(64), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_fingerprints_incident", "fingerprints", ["incident_id", "created_at"])

    op.create_table(
        "classifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("observation_window_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("final_class", sa.String(48), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("completeness", sa.Float(), nullable=False),
        sa.Column("evidence_support", sa.JSON(), nullable=False),
        sa.Column("competing_hypotheses", sa.JSON(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observation_window_id"], ["observation_windows.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("incident_id", "revision", name="uq_classification_incident_revision"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_classification_confidence"),
        sa.CheckConstraint("completeness >= 0 AND completeness <= 1", name="ck_classification_completeness"),
    )

    op.create_table(
        "evidence_certificates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("observation_window_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint_id", sa.Uuid(), nullable=False),
        sa.Column("classification_id", sa.Uuid(), nullable=False),
        sa.Column("certificate_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("scope_evidence", sa.JSON(), nullable=False),
        sa.Column("safety_inputs", sa.JSON(), nullable=False),
        sa.Column("candidate_actions", sa.JSON(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observation_window_id"], ["observation_windows.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fingerprint_id"], ["fingerprints.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["classification_id"], ["classifications.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "desired_route_states",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("admin_state", sa.String(24), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("controller_generation", sa.BigInteger(), nullable=False),
        sa.Column("source_action_id", sa.Uuid()),
        version(), *timestamps(),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["route_memberships.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("membership_id", name="uq_desired_route_membership"),
        sa.CheckConstraint("weight BETWEEN 0 AND 256", name="ck_desired_route_weight"),
    )

    op.create_table(
        "actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_certificate_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("action_kind", sa.String(48), nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("controller_generation", sa.BigInteger(), nullable=False),
        sa.Column("haproxy_backend", sa.String(80), nullable=False),
        sa.Column("haproxy_server", sa.String(80), nullable=False),
        sa.Column("previous_desired", sa.JSON(), nullable=False),
        sa.Column("previous_observed", sa.JSON(), nullable=False),
        sa.Column("requested_state", sa.JSON(), nullable=False),
        sa.Column("expected_effect", sa.String(500), nullable=False),
        sa.Column("preservation_set", sa.JSON(), nullable=False),
        sa.Column("verification_criteria", sa.JSON(), nullable=False),
        sa.Column("rollback_strategy", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True)),
        version(), *timestamps(),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_certificate_id"], ["evidence_certificates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["membership_id"], ["route_memberships.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_actions_environment_lifecycle", "actions", ["environment_id", "lifecycle", "created_at"])

    op.create_table(
        "action_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("command_hash", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("observed_state", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        *timestamps(),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("action_id", "sequence", name="uq_action_attempt_sequence"),
    )

    op.create_table(
        "observed_state_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid()),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("process_id", sa.String(80)),
        sa.Column("config_identifier", sa.String(120)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("memberships", sa.JSON(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_observed_environment_time", "observed_state_snapshots", ["environment_id", "observed_at"])

    op.create_table(
        "verification_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("affected_obligation", sa.JSON(), nullable=False),
        sa.Column("preservation_obligation", sa.JSON(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("action_id", "revision", name="uq_verification_action_revision"),
    )

    op.create_table(
        "reintegration_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_stage", sa.String(24), nullable=False),
        sa.Column("last_verified_stage", sa.String(24), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("maximum_retries", sa.Integer(), nullable=False),
        sa.Column("next_transition_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        version(), *timestamps(),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_reintegration_environment_status", "reintegration_runs", ["environment_id", "status"])

    op.create_table(
        "reintegration_stages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(24), nullable=False),
        sa.Column("requested_weight", sa.Integer()),
        sa.Column("observed_weight", sa.Integer()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("minimum_samples", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("result", sa.JSON(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["reintegration_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_reintegration_stage_sequence"),
    )

    op.create_table(
        "lab_faults",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("scenario", sa.String(48), nullable=False),
        sa.Column("target_route", sa.String(80)),
        sa.Column("target_instance", sa.String(80)),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("ground_truth_id", sa.String(80), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("cleared_at", sa.DateTime(timezone=True)),
        version(), *timestamps(),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("duration_seconds BETWEEN 5 AND 600", name="ck_lab_fault_duration"),
    )
    op.create_index("ix_lab_faults_environment_status", "lab_faults", ["environment_id", "status"])

    op.create_table(
        "controller_generations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("worker_id", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("environment_id", "generation", name="uq_controller_environment_generation"),
    )
    op.create_index("ix_controller_environment_heartbeat", "controller_generations", ["environment_id", "last_heartbeat_at"])


def downgrade() -> None:
    op.drop_index("ix_controller_environment_heartbeat", table_name="controller_generations")
    op.drop_table("controller_generations")
    op.drop_index("ix_lab_faults_environment_status", table_name="lab_faults")
    op.drop_table("lab_faults")
    op.drop_table("reintegration_stages")
    op.drop_index("ix_reintegration_environment_status", table_name="reintegration_runs")
    op.drop_table("reintegration_runs")
    op.drop_table("verification_results")
    op.drop_index("ix_observed_environment_time", table_name="observed_state_snapshots")
    op.drop_table("observed_state_snapshots")
    op.drop_table("action_attempts")
    op.drop_index("ix_actions_environment_lifecycle", table_name="actions")
    op.drop_table("actions")
    op.drop_table("desired_route_states")
    op.drop_table("evidence_certificates")
    op.drop_table("classifications")
    op.drop_index("ix_fingerprints_incident", table_name="fingerprints")
    op.drop_table("fingerprints")
    op.drop_index("ix_observation_environment_end", table_name="observation_windows")
    op.drop_table("observation_windows")
    op.drop_index("ix_incidents_environment_status", table_name="incidents")
    op.drop_table("incidents")
