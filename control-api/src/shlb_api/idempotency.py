from __future__ import annotations

import re
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shlb_api.contracts import utc_now
from shlb_api.models import IdempotencyRecord
from shlb_api.problem import ApiProblem
from shlb_api.security import canonical_hash, stable_hash

IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def require_idempotency_key(value: str | None) -> str:
    if not value or not IDEMPOTENCY_PATTERN.fullmatch(value):
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="Idempotency key required",
            detail="This command requires an Idempotency-Key containing 8–128 safe characters.",
            errors=[{"field": "Idempotency-Key", "reason": "missing or malformed"}],
        )
    return value


def find_replay(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    scope: str,
    key: str,
    request_payload: Any,
) -> IdempotencyRecord | None:
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.actor_user_id == actor_user_id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key_hash == stable_hash(key),
            IdempotencyRecord.expires_at > utc_now(),
        )
    )
    if record and record.request_hash != canonical_hash(request_payload):
        raise ApiProblem(
            status=409,
            code="IDEMPOTENCY_MISMATCH",
            title="Idempotency key reused with different input",
            detail="The key is already bound to a different canonical request.",
        )
    return record


def store_record(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    scope: str,
    key: str,
    request_payload: Any,
    response_status: int,
    response_body: dict[str, Any],
    resource_id: str | None,
    lifetime: timedelta = timedelta(hours=24),
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        actor_user_id=actor_user_id,
        scope=scope,
        key_hash=stable_hash(key),
        request_hash=canonical_hash(request_payload),
        response_status=response_status,
        response_body=response_body,
        resource_id=resource_id,
        expires_at=utc_now() + lifetime,
    )
    db.add(record)
    return record
