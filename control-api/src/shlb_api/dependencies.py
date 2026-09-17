from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from shlb_api.database import get_db
from shlb_api.models import (
    BackendInstance,
    Environment,
    Project,
    RouteGroup,
    Service,
    TeamMembership,
    User,
)
from shlb_api.problem import ApiProblem
from shlb_api.runtime import get_redis
from shlb_api.security import constant_time_equal, decode_session, session_key, unix_time
from shlb_api.settings import get_settings


@dataclass(frozen=True)
class AuthContext:
    user: User
    team_roles: dict[uuid.UUID, str]
    session_id: str
    csrf_token: str
    absolute_expires_at: int

    def role_for_team(self, team_id: uuid.UUID) -> str | None:
        return self.team_roles.get(team_id)


def get_auth_context(
    request: Request,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
) -> AuthContext:
    settings = get_settings()
    session_id = request.cookies.get(settings.cookie_name)
    if not session_id or len(session_id) > 128:
        raise ApiProblem(
            status=401,
            code="UNAUTHENTICATED",
            title="Authentication required",
            detail="A valid server-side session is required.",
            headers={"WWW-Authenticate": "Session"},
        )

    encoded = redis_client.get(session_key(session_id))
    if not encoded:
        raise ApiProblem(
            status=401,
            code="UNAUTHENTICATED",
            title="Session unavailable",
            detail="The session is missing, expired, or revoked.",
            headers={"WWW-Authenticate": "Session"},
        )

    try:
        session_payload = decode_session(encoded)
        user_id = uuid.UUID(str(session_payload["user_id"]))
        auth_version = int(session_payload["auth_version"])
        csrf_token = str(session_payload["csrf_token"])
        absolute_expires_at = int(session_payload["absolute_expires_at"])
    except (ValueError, TypeError, KeyError):
        redis_client.delete(session_key(session_id))
        raise ApiProblem(
            status=401,
            code="UNAUTHENTICATED",
            title="Session invalid",
            detail="The session contract is invalid and has been revoked.",
        ) from None

    now = unix_time()
    if absolute_expires_at <= now:
        redis_client.delete(session_key(session_id))
        raise ApiProblem(
            status=401,
            code="UNAUTHENTICATED",
            title="Session expired",
            detail="The session reached its absolute lifetime.",
        )

    user = db.scalar(select(User).where(User.id == user_id))
    if not user or user.status != "ACTIVE" or user.auth_version != auth_version:
        redis_client.delete(session_key(session_id))
        raise ApiProblem(
            status=401,
            code="UNAUTHENTICATED",
            title="Session revoked",
            detail="The account or authorization version changed.",
        )

    memberships = db.scalars(select(TeamMembership).where(TeamMembership.user_id == user.id)).all()
    team_roles = {membership.team_id: membership.role for membership in memberships}
    refresh_seconds = min(settings.session_idle_seconds, absolute_expires_at - now)
    redis_client.expire(session_key(session_id), refresh_seconds)
    return AuthContext(
        user=user,
        team_roles=team_roles,
        session_id=session_id,
        csrf_token=csrf_token,
        absolute_expires_at=absolute_expires_at,
    )


def require_csrf(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    settings = get_settings()
    supplied = request.headers.get("X-CSRF-Token", "")
    origin = request.headers.get("Origin", "").rstrip("/")
    if not supplied or not constant_time_equal(supplied, auth.csrf_token):
        raise ApiProblem(
            status=403,
            code="FORBIDDEN",
            title="CSRF validation failed",
            detail="A session-bound CSRF token is required for this mutation.",
        )
    if origin not in settings.allowed_origins:
        raise ApiProblem(
            status=403,
            code="FORBIDDEN",
            title="Origin validation failed",
            detail="The request origin is not allowed for cookie-authenticated mutation.",
        )
    return auth


def require_project(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    roles: set[str] | None = None,
) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise ApiProblem(status=404, code="NOT_FOUND", title="Project not found", detail="No such project exists.")
    role = auth.role_for_team(project.team_id)
    if role is None:
        # Scope denials intentionally look like missing resources.
        raise ApiProblem(status=404, code="NOT_FOUND", title="Project not found", detail="No such project exists.")
    if roles is not None and role not in roles:
        raise ApiProblem(
            status=403,
            code="FORBIDDEN",
            title="Insufficient project role",
            detail="The current project role cannot perform this operation.",
        )
    return project


def require_environment(
    db: Session,
    auth: AuthContext,
    environment_id: uuid.UUID,
    *,
    roles: set[str] | None = None,
) -> tuple[Environment, Project]:
    row = db.execute(
        select(Environment, Project)
        .join(Project, Project.id == Environment.project_id)
        .where(Environment.id == environment_id)
    ).one_or_none()
    if row is None:
        raise ApiProblem(
            status=404,
            code="NOT_FOUND",
            title="Environment not found",
            detail="No such environment exists.",
        )
    environment, project = row
    require_project(db, auth, project.id, roles=roles)
    return environment, project


def require_service(
    db: Session,
    auth: AuthContext,
    service_id: uuid.UUID,
    *,
    roles: set[str] | None = None,
) -> tuple[Service, Environment, Project]:
    row = db.execute(
        select(Service, Environment, Project)
        .join(Environment, Environment.id == Service.environment_id)
        .join(Project, Project.id == Environment.project_id)
        .where(Service.id == service_id)
    ).one_or_none()
    if row is None:
        raise ApiProblem(
            status=404,
            code="NOT_FOUND",
            title="Service not found",
            detail="No such service exists.",
        )
    service, environment, project = row
    require_project(db, auth, project.id, roles=roles)
    return service, environment, project


def require_route(
    db: Session,
    auth: AuthContext,
    route_id: uuid.UUID,
    *,
    roles: set[str] | None = None,
) -> tuple[RouteGroup, Service, Environment, Project]:
    row = db.execute(
        select(RouteGroup, Service, Environment, Project)
        .join(Service, Service.id == RouteGroup.service_id)
        .join(Environment, Environment.id == Service.environment_id)
        .join(Project, Project.id == Environment.project_id)
        .where(RouteGroup.id == route_id)
    ).one_or_none()
    if row is None:
        raise ApiProblem(
            status=404,
            code="NOT_FOUND",
            title="Route not found",
            detail="No such route exists.",
        )
    route, service, environment, project = row
    require_project(db, auth, project.id, roles=roles)
    return route, service, environment, project


def require_backend(
    db: Session,
    auth: AuthContext,
    backend_id: uuid.UUID,
    *,
    roles: set[str] | None = None,
) -> tuple[BackendInstance, Service, Environment, Project]:
    row = db.execute(
        select(BackendInstance, Service, Environment, Project)
        .join(Service, Service.id == BackendInstance.service_id)
        .join(Environment, Environment.id == Service.environment_id)
        .join(Project, Project.id == Environment.project_id)
        .where(BackendInstance.id == backend_id)
    ).one_or_none()
    if row is None:
        raise ApiProblem(
            status=404,
            code="NOT_FOUND",
            title="Backend not found",
            detail="No such backend exists.",
        )
    backend, service, environment, project = row
    require_project(db, auth, project.id, roles=roles)
    return backend, service, environment, project
