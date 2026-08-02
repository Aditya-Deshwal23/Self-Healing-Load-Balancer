from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shlb_api.api_helpers import (
    PROJECT_ADMIN_ROLES,
    conflict_from_integrity,
    etag,
    publish_after_commit,
    require_if_match,
)
from shlb_api.audit import add_outbox, append_audit
from shlb_api.contracts import decode_cursor, encode_cursor, list_envelope, resource_envelope
from shlb_api.database import get_db
from shlb_api.dependencies import (
    AuthContext,
    get_auth_context,
    require_csrf,
    require_environment,
    require_project,
)
from shlb_api.idempotency import find_replay, require_idempotency_key, store_record
from shlb_api.models import Environment, Project
from shlb_api.problem import ApiProblem
from shlb_api.resources import environment_resource, project_resource
from shlb_api.schemas import EnvironmentCreate, EnvironmentPatch, ProjectCreate, ProjectPatch

router = APIRouter(prefix="/api/v1", tags=["projects and environments"])


def _replay(record, response: Response):
    response.status_code = record.response_status
    response.headers["Idempotent-Replay"] = "true"
    if record.resource_id:
        response.headers["Location"] = f"/api/v1/projects/{record.resource_id}"
    return record.response_body


@router.get("/projects")
def list_projects(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    status: str | None = Query(default=None, pattern=r"^(ACTIVE|ARCHIVED)$"),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    team_ids = list(auth.team_roles)
    query = select(Project).where(Project.team_id.in_(team_ids))
    if status:
        query = query.where(Project.status == status)
    if cursor:
        try:
            cursor_time, cursor_id_raw = decode_cursor(cursor)
            cursor_id = uuid.UUID(cursor_id_raw)
        except ValueError:
            raise ApiProblem(
                status=422,
                code="VALIDATION_ERROR",
                title="Cursor is invalid",
                detail="The pagination cursor is malformed or expired.",
            ) from None
        query = query.where(
            or_(
                Project.created_at > cursor_time,
                and_(Project.created_at == cursor_time, Project.id > cursor_id),
            )
        )
    rows = db.scalars(query.order_by(Project.created_at, Project.id).limit(limit + 1)).all()
    page_rows = rows[:limit]
    next_cursor = (
        encode_cursor(page_rows[-1].created_at, str(page_rows[-1].id))
        if len(rows) > limit and page_rows
        else None
    )
    return list_envelope(
        request,
        [
            project_resource(row, role=auth.role_for_team(row.team_id))
            for row in page_rows
        ],
        limit=limit,
        next_cursor=next_cursor,
    )


@router.post("/projects", status_code=201)
def create_project(
    payload: ProjectCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    if auth.role_for_team(payload.team_id) not in PROJECT_ADMIN_ROLES:
        raise ApiProblem(
            status=403,
            code="FORBIDDEN",
            title="Insufficient team role",
            detail="A project administrator role is required to create a project.",
        )
    key = require_idempotency_key(idempotency_key)
    body = payload.model_dump(mode="json")
    scope = f"projects:create:{payload.team_id}"
    replay = find_replay(
        db,
        actor_user_id=auth.user.id,
        scope=scope,
        key=key,
        request_payload=body,
    )
    if replay:
        return _replay(replay, response)

    project = Project(
        team_id=payload.team_id,
        name=payload.name.strip(),
        slug=payload.slug,
        status="ACTIVE",
    )
    db.add(project)
    try:
        db.flush()
        data = project_resource(project, role=auth.role_for_team(project.team_id))
        response_body = resource_envelope(request, data)
        append_audit(
            db,
            project=project,
            environment_id=None,
            actor_user_id=auth.user.id,
            event_type="PROJECT_CREATED",
            subject_type="project",
            subject_id=str(project.id),
            before=None,
            after=data,
            correlation_id=request.state.correlation_id,
        )
        add_outbox(
            db,
            project_id=project.id,
            environment_id=None,
            event_type="project.created",
            aggregate_type="project",
            aggregate_id=str(project.id),
            aggregate_version=project.version,
            correlation_id=request.state.correlation_id,
            payload={"data": data},
        )
        store_record(
            db,
            actor_user_id=auth.user.id,
            scope=scope,
            key=key,
            request_payload=body,
            response_status=201,
            response_body=response_body,
            resource_id=str(project.id),
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="A project with that slug already exists in the selected team.",
        ) from exc
    response.status_code = 201
    response.headers["Location"] = f"/api/v1/projects/{project.id}"
    response.headers["ETag"] = etag(project.version)
    publish_after_commit(db, project.id)
    return response_body


@router.get("/projects/{project_id}")
def get_project(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    project = require_project(db, auth, project_id)
    response.headers["ETag"] = etag(project.version)
    return resource_envelope(
        request,
        project_resource(project, role=auth.role_for_team(project.team_id)),
    )


@router.patch("/projects/{project_id}")
def patch_project(
    project_id: uuid.UUID,
    payload: ProjectPatch,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    project = require_project(db, auth, project_id, roles=PROJECT_ADMIN_ROLES)
    require_if_match(request, project.version)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="No changes supplied",
            detail="At least one mutable project field is required.",
        )
    before = project_resource(project)
    for field, value in updates.items():
        setattr(project, field, value.strip() if isinstance(value, str) else value)
    project.version += 1
    db.flush()
    after = project_resource(project, role=auth.role_for_team(project.team_id))
    append_audit(
        db,
        project=project,
        environment_id=None,
        actor_user_id=auth.user.id,
        event_type="PROJECT_UPDATED",
        subject_type="project",
        subject_id=str(project.id),
        before=before,
        after=after,
        correlation_id=request.state.correlation_id,
    )
    add_outbox(
        db,
        project_id=project.id,
        environment_id=None,
        event_type="project.updated",
        aggregate_type="project",
        aggregate_id=str(project.id),
        aggregate_version=project.version,
        correlation_id=request.state.correlation_id,
        payload={"data": after},
    )
    db.commit()
    response.headers["ETag"] = etag(project.version)
    publish_after_commit(db, project.id)
    return resource_envelope(request, after)


@router.delete("/projects/{project_id}")
def archive_project(
    project_id: uuid.UUID,
    request: Request,
    response: Response,
    confirm: str = Query(min_length=1, max_length=16),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    project = require_project(db, auth, project_id, roles=PROJECT_ADMIN_ROLES)
    require_if_match(request, project.version)
    if confirm != "ARCHIVE":
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="Archive confirmation required",
            detail="Set confirm=ARCHIVE. Phase 2 never physically deletes project data.",
        )
    before = project_resource(project)
    project.status = "ARCHIVED"
    project.version += 1
    db.flush()
    after = project_resource(project)
    append_audit(
        db,
        project=project,
        environment_id=None,
        actor_user_id=auth.user.id,
        event_type="PROJECT_ARCHIVED",
        subject_type="project",
        subject_id=str(project.id),
        before=before,
        after=after,
        correlation_id=request.state.correlation_id,
    )
    db.commit()
    response.headers["ETag"] = etag(project.version)
    return resource_envelope(request, after)


@router.get("/projects/{project_id}/environments")
def list_environments(
    project_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_project(db, auth, project_id)
    rows = db.scalars(
        select(Environment)
        .where(Environment.project_id == project_id)
        .order_by(Environment.created_at, Environment.id)
    ).all()
    return list_envelope(
        request,
        [environment_resource(row) for row in rows],
        limit=100,
        next_cursor=None,
    )


@router.post("/projects/{project_id}/environments", status_code=201)
def create_environment(
    project_id: uuid.UUID,
    payload: EnvironmentCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    project = require_project(db, auth, project_id, roles=PROJECT_ADMIN_ROLES)
    key = require_idempotency_key(idempotency_key)
    body = payload.model_dump(mode="json")
    scope = f"environments:create:{project.id}"
    replay = find_replay(
        db,
        actor_user_id=auth.user.id,
        scope=scope,
        key=key,
        request_payload=body,
    )
    if replay:
        return _replay(replay, response)
    environment = Environment(
        project_id=project.id,
        name=payload.name.strip(),
        kind=payload.kind,
        mode=payload.mode,
        timezone=payload.timezone,
        automation_frozen=False,
        controller_generation=0,
    )
    db.add(environment)
    try:
        db.flush()
        data = environment_resource(environment)
        response_body = resource_envelope(request, data)
        append_audit(
            db,
            project=project,
            environment_id=environment.id,
            actor_user_id=auth.user.id,
            event_type="ENVIRONMENT_CREATED",
            subject_type="environment",
            subject_id=str(environment.id),
            before=None,
            after=data,
            correlation_id=request.state.correlation_id,
        )
        add_outbox(
            db,
            project_id=project.id,
            environment_id=environment.id,
            event_type="environment.created",
            aggregate_type="environment",
            aggregate_id=str(environment.id),
            aggregate_version=environment.version,
            correlation_id=request.state.correlation_id,
            payload={"data": data},
        )
        store_record(
            db,
            actor_user_id=auth.user.id,
            scope=scope,
            key=key,
            request_payload=body,
            response_status=201,
            response_body=response_body,
            resource_id=str(environment.id),
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="An environment with that name already exists in the project.",
        ) from exc
    response.status_code = 201
    response.headers["Location"] = f"/api/v1/environments/{environment.id}"
    response.headers["ETag"] = etag(environment.version)
    publish_after_commit(db, project.id)
    return response_body


@router.get("/environments/{environment_id}")
def get_environment(
    environment_id: uuid.UUID,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    environment, _ = require_environment(db, auth, environment_id)
    response.headers["ETag"] = etag(environment.version)
    return resource_envelope(request, environment_resource(environment))


@router.patch("/environments/{environment_id}")
def patch_environment(
    environment_id: uuid.UUID,
    payload: EnvironmentPatch,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    environment, project = require_environment(
        db,
        auth,
        environment_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    require_if_match(request, environment.version)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="No changes supplied",
            detail="At least one mutable environment field is required.",
        )
    before = environment_resource(environment)
    for field, value in updates.items():
        setattr(environment, field, value.strip() if isinstance(value, str) else value)
    environment.version += 1
    db.flush()
    after = environment_resource(environment)
    append_audit(
        db,
        project=project,
        environment_id=environment.id,
        actor_user_id=auth.user.id,
        event_type="ENVIRONMENT_UPDATED",
        subject_type="environment",
        subject_id=str(environment.id),
        before=before,
        after=after,
        correlation_id=request.state.correlation_id,
    )
    add_outbox(
        db,
        project_id=project.id,
        environment_id=environment.id,
        event_type="environment.updated",
        aggregate_type="environment",
        aggregate_id=str(environment.id),
        aggregate_version=environment.version,
        correlation_id=request.state.correlation_id,
        payload={"data": after},
    )
    db.commit()
    response.headers["ETag"] = etag(environment.version)
    publish_after_commit(db, project.id)
    return resource_envelope(request, after)
