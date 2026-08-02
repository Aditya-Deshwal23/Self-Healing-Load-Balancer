from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from redis import Redis
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from shlb_api.contracts import resource_envelope
from shlb_api.database import get_db
from shlb_api.dependencies import AuthContext, get_auth_context, require_environment
from shlb_api.models import (
    BackendInstance,
    Environment,
    Project,
    RouteGroup,
    RouteMembership,
    Service,
)
from shlb_api.problem import ApiProblem
from shlb_api.runtime import get_redis
from shlb_api.schemas import FailureClass

router = APIRouter(tags=["system"])


@router.get("/health/live", include_in_schema=False)
def liveness():
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
def readiness(
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    db.execute(text("SELECT 1"))
    if redis_client.ping() is not True:
        raise ApiProblem(
            status=503,
            code="DEPENDENCY_UNAVAILABLE",
            title="Redis unavailable",
            detail="The session and event dependency is unavailable.",
            retryable=True,
        )
    return {"status": "ready"}


def _default_environment(db: Session, auth: AuthContext) -> Environment:
    environment = db.scalar(
        select(Environment)
        .join(Project, Project.id == Environment.project_id)
        .where(Project.team_id.in_(list(auth.team_roles)))
        .order_by(Environment.created_at, Environment.id)
        .limit(1)
    )
    if environment is None:
        raise ApiProblem(
            status=404,
            code="NOT_FOUND",
            title="Environment not found",
            detail="No environment is available in the authorized scope.",
        )
    return environment


@router.get("/api/v1/system/status")
def system_status(
    request: Request,
    environment_id: uuid.UUID | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    environment = (
        require_environment(db, auth, environment_id)[0]
        if environment_id
        else _default_environment(db, auth)
    )
    route_count = db.scalar(
        select(func.count(RouteGroup.id))
        .join(Service, Service.id == RouteGroup.service_id)
        .where(Service.environment_id == environment.id)
    )
    backend_count = db.scalar(
        select(func.count(BackendInstance.id))
        .join(Service, Service.id == BackendInstance.service_id)
        .where(Service.environment_id == environment.id)
    )
    membership_count = db.scalar(
        select(func.count(RouteMembership.id))
        .join(RouteGroup, RouteGroup.id == RouteMembership.route_id)
        .join(Service, Service.id == RouteGroup.service_id)
        .where(Service.environment_id == environment.id)
    )
    return resource_envelope(
        request,
        {
            "environment": {
                "id": str(environment.id),
                "project_id": str(environment.project_id),
                "name": environment.name,
                "kind": environment.kind,
                "mode": environment.mode,
                "automation_frozen": environment.automation_frozen,
                "controller_generation": environment.controller_generation,
            },
            "data_plane": {
                "request_path": [
                    "NGINX",
                    "HAProxy",
                    "route-specific logical pool",
                    "physical backend instance",
                    "application dependency",
                ],
                "control_plane_in_request_path": False,
                "observed_state": "UNKNOWN",
                "reason": "Phase 2 intentionally has no HAProxy readback authority.",
            },
            "control_plane": {
                "api": "READY",
                "postgresql": "READY",
                "redis": "READY" if redis_client.ping() else "UNAVAILABLE",
                "sse": "READY",
                "worker": "NOT_DEPLOYED",
                "haproxy_access": False,
                "control_authority": "ABSENT",
            },
            "registry": {
                "route_groups": route_count or 0,
                "physical_instances": backend_count or 0,
                "logical_memberships": membership_count or 0,
                "capacity_semantics": "Physical instance capacity is counted once.",
            },
            "freshness": {
                "control_loop": "NOT_STARTED",
                "telemetry": "NOT_CONNECTED",
                "last_confirmed_state": None,
            },
        },
    )


@router.get("/api/v1/system/capabilities")
def system_capabilities(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    lab_available = (
        db.scalar(
            select(func.count(Environment.id))
            .join(Project, Project.id == Environment.project_id)
            .where(
                Project.team_id.in_(list(auth.team_roles)),
                Environment.kind == "LAB",
            )
        )
        or 0
    ) > 0
    return resource_envelope(
        request,
        {
            "phase": 2,
            "features": {
                "lab": lab_available,
                "rest_registry": True,
                "server_side_sessions": True,
                "sse": True,
                "haproxy_readback": False,
                "routing_mutations": False,
                "healing_actions": False,
            },
            "failure_classes": [item.value for item in FailureClass],
            "contracts": {
                "api": "v1",
                "fingerprint": "fingerprint-v1",
                "classification": "classification-v1",
                "event": 1,
            },
            "authority": {
                "api_process": ["registry", "policy", "identity", "audit", "event-publish"],
                "api_process_excludes": [
                    "HAProxy Runtime API",
                    "HAProxy Data Plane API",
                    "Docker socket",
                    "host execution",
                ],
            },
        },
    )
