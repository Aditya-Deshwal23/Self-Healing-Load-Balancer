from __future__ import annotations

import uuid

from fastapi import Request
from redis import RedisError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shlb_api.audit import publish_pending_outbox
from shlb_api.problem import ApiProblem
from shlb_api.runtime import get_redis

PROJECT_ADMIN_ROLES = {"PROJECT_ADMIN", "SYSTEM_ADMIN"}
OPERATOR_ROLES = {"OPERATOR", "APPROVER", "PROJECT_ADMIN", "SYSTEM_ADMIN"}


def etag(version: int) -> str:
    return f'"{version}"'


def require_if_match(request: Request, current_version: int) -> None:
    supplied = request.headers.get("If-Match")
    if supplied is None:
        raise ApiProblem(
            status=428,
            code="PRECONDITION_REQUIRED",
            title="Entity version required",
            detail="This mutation requires an If-Match entity version.",
        )
    accepted = {etag(current_version), f'W/{etag(current_version)}'}
    if supplied.strip() not in accepted:
        raise ApiProblem(
            status=412,
            code="PRECONDITION_FAILED",
            title="Entity version changed",
            detail="The supplied If-Match value does not match the current entity version.",
            headers={"ETag": etag(current_version)},
        )


def conflict_from_integrity(db: Session, exc: IntegrityError, *, detail: str) -> ApiProblem:
    db.rollback()
    return ApiProblem(
        status=409,
        code="CONFLICT",
        title="Resource conflicts with current state",
        detail=detail,
    )


def publish_after_commit(db: Session, project_id: uuid.UUID) -> None:
    try:
        publish_pending_outbox(db, get_redis(), project_id=project_id)
    except RedisError:
        # PostgreSQL outbox remains authoritative and will be retried at startup
        # or by a later successful mutation.
        db.rollback()
