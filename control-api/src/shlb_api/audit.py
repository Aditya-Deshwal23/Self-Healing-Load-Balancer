from __future__ import annotations

import json
import uuid
from typing import Any

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from shlb_api.contracts import isoformat, utc_now
from shlb_api.models import AuditEvent, EventOutbox, Project
from shlb_api.security import canonical_hash
from shlb_api.settings import get_settings


def append_audit(
    db: Session,
    *,
    project: Project,
    environment_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    event_type: str,
    subject_type: str,
    subject_id: str,
    before: Any,
    after: Any,
    correlation_id: str,
) -> AuditEvent:
    db.execute(select(Project.id).where(Project.id == project.id).with_for_update())
    latest = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.project_id == project.id)
        .order_by(AuditEvent.sequence.desc())
        .limit(1)
    )
    sequence = (latest.sequence if latest else 0) + 1
    prior_hash = latest.event_hash if latest else None
    before_hash = canonical_hash(before) if before is not None else None
    after_hash = canonical_hash(after) if after is not None else None
    event_hash = canonical_hash(
        {
            "project_id": str(project.id),
            "sequence": sequence,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "event_type": event_type,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "before_hash": before_hash,
            "after_hash": after_hash,
            "correlation_id": correlation_id,
            "prior_hash": prior_hash,
        }
    )
    audit = AuditEvent(
        project_id=project.id,
        environment_id=environment_id,
        sequence=sequence,
        actor_user_id=actor_user_id,
        event_type=event_type,
        subject_type=subject_type,
        subject_id=subject_id,
        before_hash=before_hash,
        after_hash=after_hash,
        correlation_id=correlation_id,
        prior_hash=prior_hash,
        event_hash=event_hash,
    )
    db.add(audit)
    # A single transaction may emit multiple ordered events (for example,
    # incident detection followed by classification). Flush the sequence row
    # so the next append observes it before the outer transaction commits.
    db.flush()
    return audit


def add_outbox(
    db: Session,
    *,
    project_id: uuid.UUID,
    environment_id: uuid.UUID | None,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int,
    correlation_id: str,
    payload: dict[str, Any],
) -> EventOutbox:
    row = EventOutbox(
        project_id=project_id,
        environment_id=environment_id,
        event_type=event_type,
        event_version=1,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        correlation_id=correlation_id,
        payload=payload,
    )
    db.add(row)
    return row


def event_envelope(row: EventOutbox) -> dict[str, Any]:
    published_at = row.published_at or utc_now()
    return {
        "event_id": str(row.id),
        "event_type": row.event_type,
        "event_version": row.event_version,
        "occurred_at": isoformat(row.created_at),
        "published_at": isoformat(published_at),
        "project_id": str(row.project_id),
        "environment_id": str(row.environment_id) if row.environment_id else None,
        "service_id": row.payload.get("service_id"),
        "aggregate_type": row.aggregate_type,
        "aggregate_id": row.aggregate_id,
        "aggregate_version": row.aggregate_version,
        "correlation_id": row.correlation_id,
        "incident_id": row.payload.get("incident_id"),
        "action_id": row.payload.get("action_id"),
        "data": row.payload.get("data", row.payload),
    }


def publish_pending_outbox(db: Session, redis_client: Redis, *, project_id: uuid.UUID | None = None) -> int:
    query = select(EventOutbox).where(EventOutbox.published_at.is_(None)).order_by(EventOutbox.created_at).limit(50)
    if project_id is not None:
        query = query.where(EventOutbox.project_id == project_id)
    rows = db.scalars(query).all()
    published = 0
    for row in rows:
        now = utc_now()
        row.published_at = now
        envelope = event_envelope(row)
        stream_id = redis_client.xadd(
            f"events:{row.project_id}",
            {"payload": json.dumps(envelope, separators=(",", ":"))},
            maxlen=get_settings().event_stream_max_length,
            approximate=True,
        )
        redis_client.setex(
            f"eventcursor:{row.project_id}:{row.id}",
            24 * 60 * 60,
            stream_id,
        )
        published += 1
    if published:
        db.commit()
    return published
