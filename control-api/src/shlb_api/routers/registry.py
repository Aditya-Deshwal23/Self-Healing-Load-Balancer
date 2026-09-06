from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import func, select
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
from shlb_api.contracts import list_envelope, resource_envelope
from shlb_api.database import get_db
from shlb_api.dependencies import (
    AuthContext,
    get_auth_context,
    require_backend,
    require_csrf,
    require_environment,
    require_route,
    require_service,
)
from shlb_api.idempotency import find_replay, require_idempotency_key, store_record
from shlb_api.models import (
    BackendInstance,
    DeploymentVersion,
    Environment,
    Project,
    RetryPolicy,
    RouteGroup,
    RouteMembership,
    RoutingPolicy,
    Service,
)
from shlb_api.problem import ApiProblem
from shlb_api.resources import (
    backend_resource,
    membership_resource,
    retry_policy_resource,
    route_resource,
    routing_policy_resource,
    service_resource,
    version_resource,
)
from shlb_api.schemas import (
    BackendCreate,
    BackendPatch,
    MembershipCreate,
    MembershipPatch,
    RetryPolicyCreate,
    RouteCreate,
    RoutePatch,
    RoutingPolicyCreate,
    ServiceCreate,
    VersionCreate,
)
from shlb_api.security import encrypt_field

router = APIRouter(prefix="/api/v1", tags=["topology registry"])


def _list(request: Request, rows: list[dict]):
    return list_envelope(request, rows, limit=100, next_cursor=None)


def _begin_idempotent(
    db: Session,
    *,
    auth: AuthContext,
    scope: str,
    raw_key: str | None,
    body: dict,
    response: Response,
):
    key = require_idempotency_key(raw_key)
    replay = find_replay(
        db,
        actor_user_id=auth.user.id,
        scope=scope,
        key=key,
        request_payload=body,
    )
    if replay:
        response.status_code = replay.response_status
        response.headers["Idempotent-Replay"] = "true"
        return key, replay.response_body
    return key, None


def _add_change_records(
    db: Session,
    *,
    request: Request,
    auth: AuthContext,
    project: Project,
    environment: Environment,
    event_name: str,
    subject_type: str,
    subject_id: str,
    aggregate_version: int,
    before,
    after,
) -> None:
    append_audit(
        db,
        project=project,
        environment_id=environment.id,
        actor_user_id=auth.user.id,
        event_type=event_name.upper().replace(".", "_"),
        subject_type=subject_type,
        subject_id=subject_id,
        before=before,
        after=after,
        correlation_id=request.state.correlation_id,
    )
    add_outbox(
        db,
        project_id=project.id,
        environment_id=environment.id,
        event_type=event_name,
        aggregate_type=subject_type,
        aggregate_id=subject_id,
        aggregate_version=aggregate_version,
        correlation_id=request.state.correlation_id,
        payload={"data": after},
    )


def _store_create(
    db: Session,
    *,
    request: Request,
    auth: AuthContext,
    scope: str,
    key: str,
    body: dict,
    response_body: dict,
    resource_id: uuid.UUID,
) -> None:
    store_record(
        db,
        actor_user_id=auth.user.id,
        scope=scope,
        key=key,
        request_payload=body,
        response_status=201,
        response_body=response_body,
        resource_id=str(resource_id),
    )


def _require_version_for_service(
    db: Session,
    version_id: uuid.UUID | None,
    service_id: uuid.UUID,
) -> None:
    if version_id is None:
        return
    version = db.get(DeploymentVersion, version_id)
    if version is None or version.service_id != service_id:
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="Deployment version is outside the service",
            detail="version_id must identify a deployment version owned by the backend service.",
        )


@router.get("/environments/{environment_id}/services")
def list_services(
    environment_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_environment(db, auth, environment_id)
    rows = db.scalars(
        select(Service)
        .where(Service.environment_id == environment_id)
        .order_by(Service.created_at, Service.id)
    ).all()
    return _list(request, [service_resource(row) for row in rows])


@router.post("/environments/{environment_id}/services", status_code=201)
def create_service(
    environment_id: uuid.UUID,
    payload: ServiceCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    environment, project = require_environment(
        db,
        auth,
        environment_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    body = payload.model_dump(mode="json")
    scope = f"services:create:{environment.id}"
    key, replay = _begin_idempotent(
        db,
        auth=auth,
        scope=scope,
        raw_key=idempotency_key,
        body=body,
        response=response,
    )
    if replay:
        return replay
    service = Service(
        environment_id=environment.id,
        name=payload.name.strip(),
        protocol=payload.protocol,
        status="ACTIVE",
    )
    db.add(service)
    try:
        db.flush()
        data = service_resource(service)
        response_body = resource_envelope(request, data)
        _add_change_records(
            db,
            request=request,
            auth=auth,
            project=project,
            environment=environment,
            event_name="service.created",
            subject_type="service",
            subject_id=str(service.id),
            aggregate_version=service.version,
            before=None,
            after=data,
        )
        _store_create(
            db,
            request=request,
            auth=auth,
            scope=scope,
            key=key,
            body=body,
            response_body=response_body,
            resource_id=service.id,
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="A service with that name already exists in the environment.",
        ) from exc
    response.headers["Location"] = f"/api/v1/services/{service.id}"
    response.headers["ETag"] = etag(service.version)
    publish_after_commit(db, project.id)
    return response_body


@router.get("/services/{service_id}")
def get_service(
    service_id: uuid.UUID,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    service, _, _ = require_service(db, auth, service_id)
    response.headers["ETag"] = etag(service.version)
    return resource_envelope(request, service_resource(service))


@router.get("/environments/{environment_id}/backends")
def list_backends(
    environment_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_environment(db, auth, environment_id)
    rows = db.scalars(
        select(BackendInstance)
        .join(Service, Service.id == BackendInstance.service_id)
        .where(Service.environment_id == environment_id)
        .order_by(BackendInstance.stable_name, BackendInstance.id)
    ).all()
    return _list(request, [backend_resource(row) for row in rows])


@router.post("/environments/{environment_id}/backends", status_code=201)
def create_backend(
    environment_id: uuid.UUID,
    payload: BackendCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    environment, project = require_environment(
        db,
        auth,
        environment_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    service = db.get(Service, payload.service_id)
    if service is None or service.environment_id != environment.id:
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="Service is outside the environment",
            detail="service_id must identify a service owned by the selected environment.",
        )
    _require_version_for_service(db, payload.version_id, service.id)
    body = payload.model_dump(mode="json")
    scope = f"backends:create:{environment.id}"
    key, replay = _begin_idempotent(
        db,
        auth=auth,
        scope=scope,
        raw_key=idempotency_key,
        body=body,
        response=response,
    )
    if replay:
        return replay
    backend = BackendInstance(
        service_id=service.id,
        version_id=payload.version_id,
        stable_name=payload.stable_name,
        address_ciphertext=encrypt_field(payload.address),
        port=payload.port,
        capacity=payload.capacity,
        probe_profile=payload.probe_profile,
        status="ACTIVE",
    )
    db.add(backend)
    try:
        db.flush()
        data = backend_resource(backend)
        response_body = resource_envelope(request, data)
        _add_change_records(
            db,
            request=request,
            auth=auth,
            project=project,
            environment=environment,
            event_name="backend.created",
            subject_type="backend",
            subject_id=str(backend.id),
            aggregate_version=backend.version,
            before=None,
            after=data,
        )
        _store_create(
            db,
            request=request,
            auth=auth,
            scope=scope,
            key=key,
            body=body,
            response_body=response_body,
            resource_id=backend.id,
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="The backend stable name already exists in the service.",
        ) from exc
    response.headers["Location"] = f"/api/v1/backends/{backend.id}"
    response.headers["ETag"] = etag(backend.version)
    publish_after_commit(db, project.id)
    return response_body


@router.get("/backends/{backend_id}")
def get_backend(
    backend_id: uuid.UUID,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    backend, _, _, _ = require_backend(db, auth, backend_id)
    response.headers["ETag"] = etag(backend.version)
    return resource_envelope(request, backend_resource(backend))


@router.patch("/backends/{backend_id}")
def patch_backend(
    backend_id: uuid.UUID,
    payload: BackendPatch,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    backend, _, environment, project = require_backend(
        db,
        auth,
        backend_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    require_if_match(request, backend.version)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="No changes supplied",
            detail="At least one mutable backend field is required.",
        )
    if "version_id" in updates:
        _require_version_for_service(db, updates["version_id"], backend.service_id)
    before = backend_resource(backend)
    for field, value in updates.items():
        setattr(backend, field, value)
    backend.version += 1
    db.flush()
    after = backend_resource(backend)
    _add_change_records(
        db,
        request=request,
        auth=auth,
        project=project,
        environment=environment,
        event_name="backend.updated",
        subject_type="backend",
        subject_id=str(backend.id),
        aggregate_version=backend.version,
        before=before,
        after=after,
    )
    db.commit()
    response.headers["ETag"] = etag(backend.version)
    publish_after_commit(db, project.id)
    return resource_envelope(request, after)


@router.get("/services/{service_id}/versions")
def list_versions(
    service_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_service(db, auth, service_id)
    rows = db.scalars(
        select(DeploymentVersion)
        .where(DeploymentVersion.service_id == service_id)
        .order_by(DeploymentVersion.created_at, DeploymentVersion.id)
    ).all()
    return _list(request, [version_resource(row) for row in rows])


@router.post("/services/{service_id}/versions", status_code=201)
def create_version(
    service_id: uuid.UUID,
    payload: VersionCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    service, environment, project = require_service(
        db,
        auth,
        service_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    body = payload.model_dump(mode="json")
    scope = f"versions:create:{service.id}"
    key, replay = _begin_idempotent(
        db,
        auth=auth,
        scope=scope,
        raw_key=idempotency_key,
        body=body,
        response=response,
    )
    if replay:
        return replay
    deployment = DeploymentVersion(
        service_id=service.id,
        version_label=payload.version_label,
        artifact_digest=payload.artifact_digest,
        deployed_at=payload.deployed_at,
        status="ACTIVE",
    )
    db.add(deployment)
    try:
        db.flush()
        data = version_resource(deployment)
        response_body = resource_envelope(request, data)
        _add_change_records(
            db,
            request=request,
            auth=auth,
            project=project,
            environment=environment,
            event_name="version.created",
            subject_type="deployment_version",
            subject_id=str(deployment.id),
            aggregate_version=deployment.version,
            before=None,
            after=data,
        )
        _store_create(
            db,
            request=request,
            auth=auth,
            scope=scope,
            key=key,
            body=body,
            response_body=response_body,
            resource_id=deployment.id,
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="That version label or artifact digest already exists in the service.",
        ) from exc
    response.headers["Location"] = f"/api/v1/services/{service.id}/versions"
    response.headers["ETag"] = etag(deployment.version)
    publish_after_commit(db, project.id)
    return response_body


@router.get("/services/{service_id}/routes")
def list_routes(
    service_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_service(db, auth, service_id)
    rows = db.scalars(
        select(RouteGroup)
        .where(RouteGroup.service_id == service_id)
        .order_by(RouteGroup.priority, RouteGroup.id)
    ).all()
    return _list(request, [route_resource(row) for row in rows])


@router.post("/services/{service_id}/routes", status_code=201)
def create_route(
    service_id: uuid.UUID,
    payload: RouteCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    service, environment, project = require_service(
        db,
        auth,
        service_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    body = payload.model_dump(mode="json")
    scope = f"routes:create:{service.id}"
    key, replay = _begin_idempotent(
        db,
        auth=auth,
        scope=scope,
        raw_key=idempotency_key,
        body=body,
        response=response,
    )
    if replay:
        return replay
    route = RouteGroup(service_id=service.id, **body)
    db.add(route)
    try:
        db.flush()
        data = route_resource(route)
        response_body = resource_envelope(request, data)
        _add_change_records(
            db,
            request=request,
            auth=auth,
            project=project,
            environment=environment,
            event_name="route.created",
            subject_type="route",
            subject_id=str(route.id),
            aggregate_version=route.version,
            before=None,
            after=data,
        )
        _store_create(
            db,
            request=request,
            auth=auth,
            scope=scope,
            key=key,
            body=body,
            response_body=response_body,
            resource_id=route.id,
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="The route key or priority conflicts with an existing route.",
        ) from exc
    response.headers["Location"] = f"/api/v1/routes/{route.id}"
    response.headers["ETag"] = etag(route.version)
    publish_after_commit(db, project.id)
    return response_body


@router.get("/routes/{route_id}")
def get_route(
    route_id: uuid.UUID,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    route, _, _, _ = require_route(db, auth, route_id)
    response.headers["ETag"] = etag(route.version)
    return resource_envelope(request, route_resource(route))


@router.patch("/routes/{route_id}")
def patch_route(
    route_id: uuid.UUID,
    payload: RoutePatch,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    route, _, environment, project = require_route(
        db,
        auth,
        route_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    require_if_match(request, route.version)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="No changes supplied",
            detail="At least one mutable route field is required.",
        )
    before = route_resource(route)
    for field, value in updates.items():
        setattr(route, field, value)
    route.version += 1
    try:
        db.flush()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="The requested route priority conflicts with an existing route.",
        ) from exc
    after = route_resource(route)
    _add_change_records(
        db,
        request=request,
        auth=auth,
        project=project,
        environment=environment,
        event_name="route.updated",
        subject_type="route",
        subject_id=str(route.id),
        aggregate_version=route.version,
        before=before,
        after=after,
    )
    db.commit()
    response.headers["ETag"] = etag(route.version)
    publish_after_commit(db, project.id)
    return resource_envelope(request, after)


def _membership_scope(
    db: Session,
    auth: AuthContext,
    membership_id: uuid.UUID,
    *,
    roles: set[str] | None = None,
) -> tuple[RouteMembership, RouteGroup, Service, Environment, Project]:
    membership = db.get(RouteMembership, membership_id)
    if membership is None:
        raise ApiProblem(
            status=404,
            code="NOT_FOUND",
            title="Membership not found",
            detail="No such route membership exists.",
        )
    route, service, environment, project = require_route(
        db,
        auth,
        membership.route_id,
        roles=roles,
    )
    return membership, route, service, environment, project


@router.get("/routes/{route_id}/memberships")
def list_memberships(
    route_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_route(db, auth, route_id)
    rows = db.scalars(
        select(RouteMembership)
        .where(RouteMembership.route_id == route_id)
        .order_by(RouteMembership.haproxy_server, RouteMembership.id)
    ).all()
    return _list(request, [membership_resource(row) for row in rows])


@router.post("/routes/{route_id}/memberships", status_code=201)
def create_membership(
    route_id: uuid.UUID,
    payload: MembershipCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    route, service, environment, project = require_route(
        db,
        auth,
        route_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    instance = db.get(BackendInstance, payload.instance_id)
    if instance is None or instance.service_id != service.id:
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="Backend is outside the service",
            detail="instance_id must identify a physical backend owned by the route service.",
        )
    body = payload.model_dump(mode="json")
    scope = f"memberships:create:{route.id}"
    key, replay = _begin_idempotent(
        db,
        auth=auth,
        scope=scope,
        raw_key=idempotency_key,
        body=body,
        response=response,
    )
    if replay:
        return replay
    membership = RouteMembership(
        route_id=route.id,
        instance_id=payload.instance_id,
        version_id=instance.version_id,
        haproxy_backend=payload.haproxy_backend,
        haproxy_server=payload.haproxy_server,
        baseline_weight=payload.baseline_weight,
        baseline_maxconn=payload.baseline_maxconn,
        status="ACTIVE",
    )
    db.add(membership)
    try:
        db.flush()
        data = membership_resource(membership)
        response_body = resource_envelope(request, data)
        _add_change_records(
            db,
            request=request,
            auth=auth,
            project=project,
            environment=environment,
            event_name="membership.created",
            subject_type="route_membership",
            subject_id=str(membership.id),
            aggregate_version=membership.version,
            before=None,
            after=data,
        )
        _store_create(
            db,
            request=request,
            auth=auth,
            scope=scope,
            key=key,
            body=body,
            response_body=response_body,
            resource_id=membership.id,
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="The route/backend or HAProxy backend/server pair already exists.",
        ) from exc
    response.headers["Location"] = f"/api/v1/memberships/{membership.id}"
    response.headers["ETag"] = etag(membership.version)
    publish_after_commit(db, project.id)
    return response_body


@router.get("/memberships/{membership_id}")
def get_membership(
    membership_id: uuid.UUID,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    membership, _, _, _, _ = _membership_scope(db, auth, membership_id)
    response.headers["ETag"] = etag(membership.version)
    return resource_envelope(request, membership_resource(membership))


@router.patch("/memberships/{membership_id}")
def patch_membership(
    membership_id: uuid.UUID,
    payload: MembershipPatch,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    membership, _, _, environment, project = _membership_scope(
        db,
        auth,
        membership_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    require_if_match(request, membership.version)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ApiProblem(
            status=422,
            code="VALIDATION_ERROR",
            title="No changes supplied",
            detail="At least one mutable membership field is required.",
        )
    before = membership_resource(membership)
    for field, value in updates.items():
        setattr(membership, field, value)
    membership.version += 1
    db.flush()
    after = membership_resource(membership)
    _add_change_records(
        db,
        request=request,
        auth=auth,
        project=project,
        environment=environment,
        event_name="membership.updated",
        subject_type="route_membership",
        subject_id=str(membership.id),
        aggregate_version=membership.version,
        before=before,
        after=after,
    )
    db.commit()
    response.headers["ETag"] = etag(membership.version)
    publish_after_commit(db, project.id)
    return resource_envelope(request, after)


@router.get("/routes/{route_id}/routing-policies")
def list_routing_policies(
    route_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_route(db, auth, route_id)
    rows = db.scalars(
        select(RoutingPolicy)
        .where(RoutingPolicy.route_id == route_id)
        .order_by(RoutingPolicy.revision.desc())
    ).all()
    return _list(request, [routing_policy_resource(row) for row in rows])


@router.post("/routes/{route_id}/routing-policies", status_code=201)
def create_routing_policy(
    route_id: uuid.UUID,
    payload: RoutingPolicyCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    route, _, environment, project = require_route(
        db,
        auth,
        route_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    body = payload.model_dump(mode="json")
    scope = f"routing-policies:create:{route.id}"
    key, replay = _begin_idempotent(
        db,
        auth=auth,
        scope=scope,
        raw_key=idempotency_key,
        body=body,
        response=response,
    )
    if replay:
        return replay
    active = db.scalar(
        select(RoutingPolicy).where(
            RoutingPolicy.route_id == route.id,
            RoutingPolicy.active.is_(True),
        )
    )
    if active:
        active.active = False
        db.flush()
    revision = (
        db.scalar(
            select(func.max(RoutingPolicy.revision)).where(
                RoutingPolicy.environment_id == environment.id,
                RoutingPolicy.route_id == route.id,
            )
        )
        or 0
    ) + 1
    policy = RoutingPolicy(
        environment_id=environment.id,
        route_id=route.id,
        revision=revision,
        minimum_physical_reserve=payload.minimum_physical_reserve,
        maximum_simultaneous_quarantine=payload.maximum_simultaneous_quarantine,
        verification_settings=payload.verification_settings,
        reintegration_settings=payload.reintegration_settings,
        action_allowlist=payload.action_allowlist,
        active=True,
    )
    db.add(policy)
    try:
        db.flush()
        data = routing_policy_resource(policy)
        response_body = resource_envelope(request, data)
        _add_change_records(
            db,
            request=request,
            auth=auth,
            project=project,
            environment=environment,
            event_name="routing_policy.created",
            subject_type="routing_policy",
            subject_id=str(policy.id),
            aggregate_version=policy.revision,
            before=routing_policy_resource(active) if active else None,
            after=data,
        )
        _store_create(
            db,
            request=request,
            auth=auth,
            scope=scope,
            key=key,
            body=body,
            response_body=response_body,
            resource_id=policy.id,
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="The routing policy revision conflicts with current policy state.",
        ) from exc
    response.headers["Location"] = f"/api/v1/routes/{route.id}/routing-policies"
    publish_after_commit(db, project.id)
    return response_body


@router.get("/routes/{route_id}/retry-policies")
def list_retry_policies(
    route_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_route(db, auth, route_id)
    rows = db.scalars(
        select(RetryPolicy)
        .where(RetryPolicy.route_id == route_id)
        .order_by(RetryPolicy.revision.desc())
    ).all()
    return _list(request, [retry_policy_resource(row) for row in rows])


@router.post("/routes/{route_id}/retry-policies", status_code=201)
def create_retry_policy(
    route_id: uuid.UUID,
    payload: RetryPolicyCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    route, _, environment, project = require_route(
        db,
        auth,
        route_id,
        roles=PROJECT_ADMIN_ROLES,
    )
    body = payload.model_dump(mode="json")
    scope = f"retry-policies:create:{route.id}"
    key, replay = _begin_idempotent(
        db,
        auth=auth,
        scope=scope,
        raw_key=idempotency_key,
        body=body,
        response=response,
    )
    if replay:
        return replay
    active = db.scalar(
        select(RetryPolicy).where(
            RetryPolicy.route_id == route.id,
            RetryPolicy.active.is_(True),
        )
    )
    if active:
        active.active = False
        db.flush()
    revision = (
        db.scalar(
            select(func.max(RetryPolicy.revision)).where(
                RetryPolicy.route_id == route.id,
            )
        )
        or 0
    ) + 1
    policy = RetryPolicy(
        route_id=route.id,
        revision=revision,
        method_category=payload.method_category,
        allowed_failures=payload.allowed_failures,
        maximum_cross_instance_retries=payload.maximum_cross_instance_retries,
        ambiguous_post_behavior=payload.ambiguous_post_behavior,
        active=True,
    )
    db.add(policy)
    try:
        db.flush()
        data = retry_policy_resource(policy)
        response_body = resource_envelope(request, data)
        _add_change_records(
            db,
            request=request,
            auth=auth,
            project=project,
            environment=environment,
            event_name="retry_policy.created",
            subject_type="retry_policy",
            subject_id=str(policy.id),
            aggregate_version=policy.revision,
            before=retry_policy_resource(active) if active else None,
            after=data,
        )
        _store_create(
            db,
            request=request,
            auth=auth,
            scope=scope,
            key=key,
            body=body,
            response_body=response_body,
            resource_id=policy.id,
        )
        db.commit()
    except IntegrityError as exc:
        raise conflict_from_integrity(
            db,
            exc,
            detail="The retry policy revision conflicts with current policy state.",
        ) from exc
    response.headers["Location"] = f"/api/v1/routes/{route.id}/retry-policies"
    publish_after_commit(db, project.id)
    return response_body
