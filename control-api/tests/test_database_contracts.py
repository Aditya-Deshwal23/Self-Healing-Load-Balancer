from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from shlb_api.database import get_session_factory
from shlb_api.models import (
    AuditEvent,
    BackendInstance,
    EventOutbox,
    Project,
    RouteMembership,
)
from shlb_api.security import encrypt_field


def test_seed_preserves_physical_capacity_and_logical_membership_counts() -> None:
    with get_session_factory()() as db:
        assert db.scalar(select(func.count(BackendInstance.id))) == 3
        assert db.scalar(select(func.sum(BackendInstance.capacity))) == 300
        assert db.scalar(select(func.count(RouteMembership.id))) == 12


def test_backend_addresses_are_encrypted_at_rest() -> None:
    with get_session_factory()() as db:
        rows = db.scalars(select(BackendInstance)).all()
        assert rows
        assert all(b"demo-backend" not in row.address_ciphertext for row in rows)


def test_postgres_capacity_constraint_is_enforced() -> None:
    with get_session_factory()() as db:
        row = BackendInstance(
            id=uuid.uuid4(),
            service_id=uuid.UUID("50000000-0000-4000-8000-000000000001"),
            version_id=uuid.UUID("60000000-0000-4000-8000-000000000001"),
            stable_name=f"invalid-{uuid.uuid4()}",
            address_ciphertext=encrypt_field("invalid-backend"),
            port=8080,
            capacity=0,
            probe_profile="healthz",
            status="ACTIVE",
        )
        db.add(row)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_seeded_audit_and_outbox_contracts_exist() -> None:
    with get_session_factory()() as db:
        project_id = uuid.UUID("30000000-0000-4000-8000-000000000001")
        audits = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.project_id == project_id)
            .order_by(AuditEvent.sequence)
        ).all()
        assert audits
        assert audits[0].sequence == 1
        assert audits[0].prior_hash is None
        assert len(audits[0].event_hash) == 64
        assert db.scalar(
            select(func.count(EventOutbox.id)).where(EventOutbox.project_id == project_id)
        ) >= 1


def test_foreign_project_exists_without_bootstrap_user_scope() -> None:
    with get_session_factory()() as db:
        project = db.get(
            Project,
            uuid.UUID("30000000-0000-4000-8000-000000000099"),
        )
        assert project is not None
