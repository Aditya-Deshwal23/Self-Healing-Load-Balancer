from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from shlb_api.api_helpers import etag, publish_after_commit, require_if_match
from shlb_api.audit import add_outbox, append_audit
from shlb_api.contracts import isoformat, resource_envelope, utc_now
from shlb_api.database import get_db
from shlb_api.dependencies import AuthContext, get_auth_context, require_csrf, require_environment
from shlb_api.idempotency import find_replay, require_idempotency_key, store_record
from shlb_api.models import (
    Action,
    ActionAttempt,
    BackendInstance,
    Classification,
    ControllerGeneration,
    DesiredRouteState,
    Environment,
    EvidenceCertificate,
    Fingerprint,
    Incident,
    LabFault,
    LabResetRequest,
    ObservationWindow,
    ObservedStateSnapshot,
    ReintegrationRun,
    ReintegrationStage,
    RouteGroup,
    RouteMembership,
    Service,
    VerificationResult,
)
from shlb_api.problem import ApiProblem
from shlb_api.schemas import LabFaultCreate
from shlb_api.worker_policy import LAB_POLICY

router = APIRouter(prefix="/api/v1", tags=["operations"])
LAB_ROLES = {"RESEARCHER", "PROJECT_ADMIN", "SYSTEM_ADMIN"}
TERMINAL_FAULT_STATES = {"CLEARED", "EXPIRED", "FAILED"}
ACTIVE_INCIDENT_STATES = {"OPEN", "MITIGATING", "VERIFYING", "RECOVERING", "NEEDS_REVIEW"}


def _incident_data(db: Session, row: Incident) -> dict:
    route = db.get(RouteGroup, row.route_id) if row.route_id else None
    instance = db.get(BackendInstance, row.instance_id) if row.instance_id else None
    return {
        "id": str(row.id),
        "environment_id": str(row.environment_id),
        "route_id": str(row.route_id) if row.route_id else None,
        "instance_id": str(row.instance_id) if row.instance_id else None,
        "target": {
            "route": route.route_key if route else None,
            "instance": instance.stable_name if instance else None,
        },
        "status": row.status,
        "severity": row.severity,
        "classification": row.operational_class,
        "fingerprint_hash": row.fingerprint_hash,
        "summary": row.summary,
        "opened_at": isoformat(row.opened_at),
        "last_observed_at": isoformat(row.last_observed_at),
        "resolved_at": isoformat(row.resolved_at) if row.resolved_at else None,
        "version": row.version,
    }


def _action_data(row: Action, attempts: list[ActionAttempt] | None = None) -> dict:
    return {
        "id": str(row.id),
        "environment_id": str(row.environment_id),
        "incident_id": str(row.incident_id),
        "evidence_certificate_id": str(row.evidence_certificate_id),
        "membership_id": str(row.membership_id),
        "kind": row.action_kind,
        "lifecycle": row.lifecycle,
        "controller_generation": row.controller_generation,
        "target": {"backend": row.haproxy_backend, "server": row.haproxy_server},
        "previous_desired": row.previous_desired,
        "previous_observed": row.previous_observed,
        "requested_state": row.requested_state,
        "expected_effect": row.expected_effect,
        "preservation_set": row.preservation_set,
        "verification_criteria": row.verification_criteria,
        "rollback_strategy": row.rollback_strategy,
        "expires_at": isoformat(row.expires_at),
        "terminal_at": isoformat(row.terminal_at) if row.terminal_at else None,
        "version": row.version,
        "attempts": [
            {
                "id": str(attempt.id),
                "sequence": attempt.sequence,
                "operation": attempt.operation,
                "status": attempt.status,
                "issued_at": isoformat(attempt.issued_at),
                "completed_at": isoformat(attempt.completed_at) if attempt.completed_at else None,
                "response": attempt.response,
                "observed_state": attempt.observed_state,
                "error_code": attempt.error_code,
            }
            for attempt in (attempts or [])
        ],
    }


def _fault_data(row: LabFault) -> dict:
    return {
        "id": str(row.id),
        "environment_id": str(row.environment_id),
        "scenario": row.scenario,
        "scenario_kind": row.scenario_kind,
        "target": {"route": row.target_route, "instance": row.target_instance},
        "duration_seconds": row.duration_seconds,
        "status": row.status,
        "ground_truth_id": row.ground_truth_id,
        "expires_at": isoformat(row.expires_at),
        "applied_at": isoformat(row.applied_at) if row.applied_at else None,
        "cleared_at": isoformat(row.cleared_at) if row.cleared_at else None,
        "version": row.version,
    }


def _lab_reset_data(row: LabResetRequest) -> dict:
    return {
        "id": str(row.id),
        "status": row.status,
        "result": row.result,
        "created_at": isoformat(row.created_at),
        "completed_at": isoformat(row.completed_at) if row.completed_at else None,
    }


def _route_rows(db: Session, environment_id: uuid.UUID):
    return db.execute(
        select(RouteMembership, RouteGroup, BackendInstance, DesiredRouteState)
        .join(RouteGroup, RouteGroup.id == RouteMembership.route_id)
        .join(Service, Service.id == RouteGroup.service_id)
        .join(BackendInstance, BackendInstance.id == RouteMembership.instance_id)
        .outerjoin(DesiredRouteState, DesiredRouteState.membership_id == RouteMembership.id)
        .where(Service.environment_id == environment_id)
        .order_by(RouteGroup.priority, BackendInstance.stable_name)
    ).all()


@router.get("/environments/{environment_id}/operational-summary")
def operational_summary(environment_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    environment, _ = require_environment(db, auth, environment_id)
    latest_window = db.scalar(select(ObservationWindow).where(ObservationWindow.environment_id == environment.id).order_by(ObservationWindow.ended_at.desc()).limit(1))
    latest_snapshot = db.scalar(select(ObservedStateSnapshot).where(ObservedStateSnapshot.environment_id == environment.id).order_by(ObservedStateSnapshot.observed_at.desc()).limit(1))
    active_incidents = db.scalars(select(Incident).where(Incident.environment_id == environment.id, Incident.status.in_(ACTIVE_INCIDENT_STATES)).order_by(Incident.opened_at.desc())).all()
    current_action = db.scalar(select(Action).where(Action.environment_id == environment.id, Action.lifecycle.not_in(["COMMITTED", "ROLLED_BACK", "FAILED", "NEEDS_REVIEW"])).order_by(Action.created_at.desc()).limit(1))
    generation = db.scalar(select(ControllerGeneration).where(ControllerGeneration.environment_id == environment.id).order_by(ControllerGeneration.generation.desc()).limit(1))
    latest_reset = db.scalar(select(LabResetRequest).where(LabResetRequest.environment_id == environment.id).order_by(LabResetRequest.created_at.desc()).limit(1))
    metrics = latest_window.metrics if latest_window else {}
    return resource_envelope(request, {
        "environment": {"id": str(environment.id), "name": environment.name, "kind": environment.kind, "mode": environment.mode, "automation_frozen": environment.automation_frozen, "controller_generation": environment.controller_generation},
        "traffic": metrics.get("summary", {"admitted_rps": None, "success_ratio": None, "healthy_capacity_percent": None}),
        "active_incidents": [_incident_data(db, row) for row in active_incidents],
        "current_action": _action_data(current_action) if current_action else None,
        "freshness": {"evidence_window_ended_at": isoformat(latest_window.ended_at) if latest_window else None, "observed_state_at": isoformat(latest_snapshot.observed_at) if latest_snapshot else None, "completeness": latest_window.completeness if latest_window else 0},
        "worker": {"status": generation.status if generation else "NOT_STARTED", "generation": generation.generation if generation else None, "last_heartbeat_at": isoformat(generation.last_heartbeat_at) if generation else None},
        "lab_reset": _lab_reset_data(latest_reset) if latest_reset else None,
    })


@router.get("/environments/{environment_id}/traffic-history")
def traffic_history(environment_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    environment, _ = require_environment(db, auth, environment_id)
    rows = db.scalars(
        select(ObservationWindow)
        .where(
            ObservationWindow.environment_id == environment.id,
            ObservationWindow.ended_at >= utc_now() - timedelta(seconds=120),
        )
        .order_by(ObservationWindow.ended_at.desc())
        .limit(240)
    ).all()
    bucket_seconds = 5
    buckets: dict[int, dict] = {}
    routes = ("public", "auth", "catalog", "checkout")
    instances = ("inst-a", "inst-b", "inst-c")
    for window in reversed(rows):
        timestamp = int(window.ended_at.timestamp())
        bucket_at = timestamp - timestamp % bucket_seconds
        bucket = buckets.setdefault(bucket_at, {
            "routes": {
                route: {"samples": 0, "errors": 0, "p95_values": [], "observations": 0}
                for route in routes
            },
        })
        memberships = window.metrics.get("memberships", {})
        for route in routes:
            values = bucket["routes"][route]
            for instance in instances:
                member = memberships.get(f"{route}/{instance}", {})
                values["samples"] += int(member.get("samples") or 0)
                values["errors"] += int(member.get("errors") or 0)
                if member.get("p95_ms") is not None:
                    values["p95_values"].append(float(member["p95_ms"]))
            values["observations"] += 1
    points = []
    for bucket_at, bucket in buckets.items():
        route_points = {}
        for route, values in bucket["routes"].items():
            samples = values["samples"]
            observations = values["observations"]
            route_points[route] = {
                "requests_per_second": round(samples / (LAB_POLICY.observation_window_seconds * observations), 2) if observations else None,
                "errors_per_second": round(values["errors"] / (LAB_POLICY.observation_window_seconds * observations), 2) if observations else None,
                "error_rate": round(values["errors"] / samples, 4) if samples else None,
                "worst_instance_p95_ms": round(max(values["p95_values"]), 2) if values["p95_values"] else None,
                "samples": round(samples / observations) if observations else 0,
            }
        points.append({
            "at": isoformat(datetime.fromtimestamp(bucket_at, tz=rows[-1].ended_at.tzinfo)),
            "routes": route_points,
        })
    return resource_envelope(request, {
        "range_seconds": 120,
        "bucket_seconds": bucket_seconds,
        "observation_window_seconds": LAB_POLICY.observation_window_seconds,
        "points": points,
    })


@router.get("/environments/{environment_id}/matrix")
def matrix(environment_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    environment, _ = require_environment(db, auth, environment_id)
    latest_window = db.scalar(select(ObservationWindow).where(ObservationWindow.environment_id == environment.id).order_by(ObservationWindow.ended_at.desc()).limit(1))
    latest_snapshot = db.scalar(select(ObservedStateSnapshot).where(ObservedStateSnapshot.environment_id == environment.id).order_by(ObservedStateSnapshot.observed_at.desc()).limit(1))
    observed = {(item["backend"], item["server"]): item for item in (latest_snapshot.memberships if latest_snapshot else [])}
    evidence = (latest_window.metrics.get("memberships", {}) if latest_window else {})
    incidents = db.scalars(select(Incident).where(Incident.environment_id == environment.id, Incident.status.in_(ACTIVE_INCIDENT_STATES))).all()
    incident_map = {(str(row.route_id), str(row.instance_id)): str(row.id) for row in incidents}
    rows = []
    for membership, route, instance, desired in _route_rows(db, environment.id):
        key = f"{route.route_key}/{instance.stable_name}"
        state = observed.get((membership.haproxy_backend, membership.haproxy_server))
        metric = evidence.get(key, {})
        desired_state = {"admin": desired.admin_state, "weight": desired.weight} if desired else {"admin": "unknown", "weight": None}
        rows.append({
            "membership_id": str(membership.id), "route_id": str(route.id), "route": route.route_key, "criticality": route.criticality,
            "instance_id": str(instance.id), "instance": instance.stable_name, "capacity": instance.capacity,
            "haproxy_backend": membership.haproxy_backend, "haproxy_server": membership.haproxy_server,
            "desired": desired_state, "observed": state,
            "drift": state is None or state.get("weight") != desired_state["weight"] or state.get("admin_state") != desired_state["admin"],
            "evidence": metric, "direct_probe": latest_window.probes.get(key, {}) if latest_window else {},
            "incident_id": incident_map.get((str(route.id), str(instance.id))),
        })
    return resource_envelope(request, {"environment_id": str(environment.id), "observed_at": isoformat(latest_snapshot.observed_at) if latest_snapshot else None, "evidence_window_ended_at": isoformat(latest_window.ended_at) if latest_window else None, "cells": rows})


@router.get("/environments/{environment_id}/incidents")
def incidents(environment_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    require_environment(db, auth, environment_id)
    rows = db.scalars(select(Incident).where(Incident.environment_id == environment_id).order_by(Incident.opened_at.desc()).limit(100)).all()
    return resource_envelope(request, {"items": [_incident_data(db, row) for row in rows]})


def _authorized_incident(db: Session, auth: AuthContext, incident_id: uuid.UUID) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident:
        raise ApiProblem(status=404, code="NOT_FOUND", title="Incident not found", detail="No such incident exists.")
    require_environment(db, auth, incident.environment_id)
    return incident


@router.get("/incidents/{incident_id}")
def incident_detail(incident_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    incident = _authorized_incident(db, auth, incident_id)
    return resource_envelope(request, _incident_data(db, incident))


@router.get("/incidents/{incident_id}/decision-trace")
def decision_trace(incident_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    incident = _authorized_incident(db, auth, incident_id)
    classifications = db.scalars(select(Classification).where(Classification.incident_id == incident.id).order_by(Classification.revision)).all()
    fingerprint = db.scalar(select(Fingerprint).where(Fingerprint.incident_id == incident.id).order_by(Fingerprint.created_at.desc()).limit(1))
    certificate = db.scalar(select(EvidenceCertificate).where(EvidenceCertificate.incident_id == incident.id).order_by(EvidenceCertificate.created_at.desc()).limit(1))
    window = db.get(ObservationWindow, certificate.observation_window_id) if certificate else None
    action = db.scalar(select(Action).where(Action.incident_id == incident.id).order_by(Action.created_at.desc()).limit(1))
    attempts = db.scalars(select(ActionAttempt).where(ActionAttempt.action_id == action.id).order_by(ActionAttempt.sequence)).all() if action else []
    verification = db.scalar(select(VerificationResult).join(Action, Action.id == VerificationResult.action_id).where(Action.incident_id == incident.id).order_by(VerificationResult.revision.desc()).limit(1))
    recovery = db.scalar(select(ReintegrationRun).where(ReintegrationRun.incident_id == incident.id).order_by(ReintegrationRun.created_at.desc()).limit(1))
    lab_fault = db.scalar(
        select(LabFault)
        .where(
            LabFault.environment_id == incident.environment_id,
            LabFault.applied_at.is_not(None),
            LabFault.applied_at <= window.ended_at,
            LabFault.expires_at >= window.started_at,
            or_(LabFault.cleared_at.is_(None), LabFault.cleared_at >= window.started_at),
        )
        .order_by(LabFault.applied_at.desc())
        .limit(1)
    ) if window else None
    return resource_envelope(request, {
        "incident": _incident_data(db, incident),
        "evidence": {"window_id": str(window.id), "started_at": isoformat(window.started_at), "ended_at": isoformat(window.ended_at), "completeness": window.completeness, "metrics": window.metrics, "probes": window.probes, "conflicts": window.conflicts} if window else None,
        "lab_fault": {"id": str(lab_fault.id), "scenario": lab_fault.scenario, "scenario_kind": lab_fault.scenario_kind, "target": {"route": lab_fault.target_route, "instance": lab_fault.target_instance}, "duration_seconds": lab_fault.duration_seconds, "status": lab_fault.status, "ground_truth_id": lab_fault.ground_truth_id, "applied_at": isoformat(lab_fault.applied_at) if lab_fault.applied_at else None, "expires_at": isoformat(lab_fault.expires_at), "cleared_at": isoformat(lab_fault.cleared_at) if lab_fault.cleared_at else None} if lab_fault else None,
        "fingerprint": {"id": str(fingerprint.id), "schema_version": fingerprint.schema_version, "hash": fingerprint.fingerprint_hash, "canonical": fingerprint.canonical_value} if fingerprint else None,
        "classifications": [{"id": str(row.id), "revision": row.revision, "final_class": row.final_class, "confidence": row.confidence, "completeness": row.completeness, "evidence_support": row.evidence_support, "competing_hypotheses": row.competing_hypotheses} for row in classifications],
        "certificate": {"id": str(certificate.id), "hash": certificate.certificate_hash, "scope_evidence": certificate.scope_evidence, "safety_inputs": certificate.safety_inputs, "candidate_actions": certificate.candidate_actions} if certificate else None,
        "action": _action_data(action, attempts) if action else None,
        "verification": {"result": verification.result, "affected": verification.affected_obligation, "preservation": verification.preservation_obligation, "sample_count": verification.sample_count, "completed_at": isoformat(verification.completed_at) if verification.completed_at else None} if verification else None,
        "recovery": {"id": str(recovery.id), "status": recovery.status, "current_stage": recovery.current_stage, "last_verified_stage": recovery.last_verified_stage} if recovery else None,
    })


@router.get("/environments/{environment_id}/actions")
def actions(environment_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    require_environment(db, auth, environment_id)
    rows = db.scalars(select(Action).where(Action.environment_id == environment_id).order_by(Action.created_at.desc()).limit(100)).all()
    return resource_envelope(request, {"items": [_action_data(row) for row in rows]})


@router.get("/actions/{action_id}")
def action_detail(action_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    action = db.get(Action, action_id)
    if not action:
        raise ApiProblem(status=404, code="NOT_FOUND", title="Action not found", detail="No such action exists.")
    require_environment(db, auth, action.environment_id)
    attempts = db.scalars(select(ActionAttempt).where(ActionAttempt.action_id == action.id).order_by(ActionAttempt.sequence)).all()
    verification = db.scalars(select(VerificationResult).where(VerificationResult.action_id == action.id).order_by(VerificationResult.revision)).all()
    data = _action_data(action, attempts)
    data["verification"] = [{"revision": row.revision, "result": row.result, "affected": row.affected_obligation, "preservation": row.preservation_obligation, "sample_count": row.sample_count, "completed_at": isoformat(row.completed_at) if row.completed_at else None} for row in verification]
    return resource_envelope(request, data)


@router.get("/environments/{environment_id}/reintegration")
def reintegration_list(environment_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    require_environment(db, auth, environment_id)
    rows = db.scalars(select(ReintegrationRun).where(ReintegrationRun.environment_id == environment_id).order_by(ReintegrationRun.created_at.desc()).limit(100)).all()
    return resource_envelope(request, {"items": [{"id": str(row.id), "incident_id": str(row.incident_id), "action_id": str(row.action_id), "status": row.status, "current_stage": row.current_stage, "last_verified_stage": row.last_verified_stage, "retry_count": row.retry_count, "maximum_retries": row.maximum_retries, "next_transition_at": isoformat(row.next_transition_at) if row.next_transition_at else None, "version": row.version} for row in rows]})


@router.get("/reintegration/{run_id}")
def reintegration_detail(run_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    run = db.get(ReintegrationRun, run_id)
    if not run:
        raise ApiProblem(status=404, code="NOT_FOUND", title="Reintegration run not found", detail="No such run exists.")
    require_environment(db, auth, run.environment_id)
    stages = db.scalars(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id).order_by(ReintegrationStage.sequence)).all()
    return resource_envelope(request, {"id": str(run.id), "incident_id": str(run.incident_id), "action_id": str(run.action_id), "status": run.status, "current_stage": run.current_stage, "last_verified_stage": run.last_verified_stage, "retry_count": run.retry_count, "maximum_retries": run.maximum_retries, "next_transition_at": isoformat(run.next_transition_at) if run.next_transition_at else None, "version": run.version, "stages": [{"id": str(stage.id), "sequence": stage.sequence, "name": stage.name, "requested_weight": stage.requested_weight, "observed_weight": stage.observed_weight, "status": stage.status, "sample_count": stage.sample_count, "minimum_samples": stage.minimum_samples, "started_at": isoformat(stage.started_at) if stage.started_at else None, "verified_at": isoformat(stage.verified_at) if stage.verified_at else None, "result": stage.result} for stage in stages]})


@router.get("/environments/{environment_id}/lab/faults")
def list_faults(environment_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    environment, _ = require_environment(db, auth, environment_id)
    if environment.kind != "LAB":
        raise ApiProblem(status=404, code="NOT_FOUND", title="LAB faults unavailable", detail="Fault resources exist only in LAB environments.")
    rows = db.scalars(select(LabFault).where(LabFault.environment_id == environment.id).order_by(LabFault.created_at.desc()).limit(100)).all()
    return resource_envelope(request, {"items": [_fault_data(row) for row in rows]})


@router.post("/environments/{environment_id}/lab/reset", status_code=202)
def reset_lab(environment_id: uuid.UUID, request: Request, response: Response, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), auth: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    environment, project = require_environment(db, auth, environment_id, roles=LAB_ROLES)
    if environment.kind != "LAB":
        raise ApiProblem(status=404, code="NOT_FOUND", title="LAB reset unavailable", detail="Baseline reset is available only in LAB environments.")
    db.execute(select(Environment.id).where(Environment.id == environment.id).with_for_update())
    key = require_idempotency_key(idempotency_key)
    body = {"environment_id": str(environment.id), "command": "restore_lab_baseline"}
    scope = f"lab-reset:{environment.id}"
    replay = find_replay(db, actor_user_id=auth.user.id, scope=scope, key=key, request_payload=body)
    if replay:
        response.status_code = replay.response_status
        response.headers["Idempotent-Replay"] = "true"
        return replay.response_body
    pending = db.scalar(select(LabResetRequest).where(LabResetRequest.environment_id == environment.id, LabResetRequest.status.in_(["REQUESTED", "RUNNING"])).order_by(LabResetRequest.created_at.desc()).limit(1))
    if pending:
        raise ApiProblem(status=409, code="CONFLICT", title="LAB reset already running", detail="Wait for the current baseline reset to finish before requesting another.")
    reset = LabResetRequest(environment_id=environment.id, requested_by=auth.user.id, status="REQUESTED", result={})
    db.add(reset)
    db.flush()
    data = _lab_reset_data(reset)
    response_body = resource_envelope(request, data)
    append_audit(db, project=project, environment_id=environment.id, actor_user_id=auth.user.id, event_type="LAB_RESET_REQUESTED", subject_type="lab_reset", subject_id=str(reset.id), before=None, after=data, correlation_id=request.state.correlation_id)
    add_outbox(db, project_id=project.id, environment_id=environment.id, event_type="lab_reset_requested", aggregate_type="lab_reset", aggregate_id=str(reset.id), aggregate_version=reset.version, correlation_id=request.state.correlation_id, payload={"data": data})
    store_record(db, actor_user_id=auth.user.id, scope=scope, key=key, request_payload=body, response_status=202, response_body=response_body, resource_id=str(reset.id))
    db.commit()
    response.headers["Location"] = f"/api/v1/environments/{environment.id}/operational-summary"
    response.headers["ETag"] = etag(reset.version)
    publish_after_commit(db, project.id)
    return response_body


@router.post("/environments/{environment_id}/lab/faults", status_code=202)
def create_fault(environment_id: uuid.UUID, payload: LabFaultCreate, request: Request, response: Response, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), auth: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    environment, project = require_environment(db, auth, environment_id, roles=LAB_ROLES)
    if environment.kind != "LAB":
        raise ApiProblem(status=404, code="NOT_FOUND", title="LAB faults unavailable", detail="Fault resources exist only in LAB environments.")
    active = db.scalar(select(func.count(LabFault.id)).where(LabFault.environment_id == environment.id, LabFault.status.not_in(TERMINAL_FAULT_STATES))) or 0
    if active:
        raise ApiProblem(status=409, code="CONFLICT", title="A LAB fault is already active", detail="Clear the current bounded fault before starting another scenario.")
    key = require_idempotency_key(idempotency_key)
    body = payload.model_dump(mode="json")
    scope = f"lab-fault:create:{environment.id}"
    replay = find_replay(db, actor_user_id=auth.user.id, scope=scope, key=key, request_payload=body)
    if replay:
        response.status_code = replay.response_status
        response.headers["Idempotent-Replay"] = "true"
        return replay.response_body
    legacy_faults = {
        "CHECKOUT_INST_B_FAILURE": ("route_failure", "checkout", "inst-b"),
        "AUTH_INST_A_FAILURE": ("route_failure", "auth", "inst-a"),
        "GRAY_FAILURE_INST_A": ("gray_failure", None, "inst-a"),
        "INST_B_DOWN": ("instance_down", None, "inst-b"),
        "SHARED_CHECKOUT_FAILURE": ("route_failure", "checkout", "all"),
        "UNKNOWN_CONFLICT": ("unknown_conflict", "checkout", "inst-b"),
    }
    legacy = legacy_faults.get(payload.scenario)
    if legacy:
        scenario_kind, legacy_route, legacy_instance = legacy
        scenario_kind = payload.scenario_kind or scenario_kind
        target_route = payload.target_route if payload.target_route is not None else legacy_route
        target_instance = payload.target_instance if payload.target_instance is not None else legacy_instance
    else:
        if payload.scenario_kind is None:
            raise ApiProblem(status=422, code="INVALID_FAULT", title="Scenario kind is required", detail="Generic LAB scenarios must provide scenario_kind.")
        scenario_kind = payload.scenario_kind
        target_route = payload.target_route
        target_instance = payload.target_instance
    fault = LabFault(environment_id=environment.id, scenario=payload.scenario, scenario_kind=scenario_kind, target_route=target_route, target_instance=target_instance, duration_seconds=payload.duration_seconds, requested_by=auth.user.id, status="REQUESTED", ground_truth_id=f"gt-{uuid.uuid4().hex[:20]}", expires_at=utc_now() + timedelta(seconds=payload.duration_seconds))
    db.add(fault)
    db.flush()
    data = _fault_data(fault)
    response_body = resource_envelope(request, data)
    append_audit(db, project=project, environment_id=environment.id, actor_user_id=auth.user.id, event_type="LAB_FAULT_REQUESTED", subject_type="lab_fault", subject_id=str(fault.id), before=None, after=data, correlation_id=request.state.correlation_id)
    add_outbox(db, project_id=project.id, environment_id=environment.id, event_type="lab_fault_requested", aggregate_type="lab_fault", aggregate_id=str(fault.id), aggregate_version=fault.version, correlation_id=request.state.correlation_id, payload={"data": data})
    store_record(db, actor_user_id=auth.user.id, scope=scope, key=key, request_payload=body, response_status=202, response_body=response_body, resource_id=str(fault.id))
    db.commit()
    response.headers["Location"] = f"/api/v1/environments/{environment.id}/lab/faults"
    response.headers["ETag"] = etag(fault.version)
    publish_after_commit(db, project.id)
    return response_body


@router.delete("/lab/faults/{fault_id}", status_code=202)
def clear_fault(fault_id: uuid.UUID, request: Request, response: Response, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), auth: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    fault = db.get(LabFault, fault_id)
    if not fault:
        raise ApiProblem(status=404, code="NOT_FOUND", title="LAB fault not found", detail="No such LAB fault exists.")
    environment, project = require_environment(db, auth, fault.environment_id, roles=LAB_ROLES)
    if environment.kind != "LAB":
        raise ApiProblem(status=404, code="NOT_FOUND", title="LAB faults unavailable", detail="Fault resources exist only in LAB environments.")
    require_if_match(request, fault.version)
    key = require_idempotency_key(idempotency_key)
    body = {"fault_id": str(fault.id), "version": fault.version, "command": "clear"}
    scope = f"lab-fault:clear:{fault.id}"
    replay = find_replay(db, actor_user_id=auth.user.id, scope=scope, key=key, request_payload=body)
    if replay:
        response.status_code = replay.response_status
        response.headers["Idempotent-Replay"] = "true"
        return replay.response_body
    if fault.status in TERMINAL_FAULT_STATES:
        raise ApiProblem(status=409, code="CONFLICT", title="LAB fault already terminal", detail="The fault is already cleared, expired, or failed.")
    before = _fault_data(fault)
    fault.status = "CLEAR_REQUESTED"
    fault.version += 1
    db.flush()
    data = _fault_data(fault)
    response_body = resource_envelope(request, data)
    append_audit(db, project=project, environment_id=environment.id, actor_user_id=auth.user.id, event_type="LAB_FAULT_CLEAR_REQUESTED", subject_type="lab_fault", subject_id=str(fault.id), before=before, after=data, correlation_id=request.state.correlation_id)
    add_outbox(db, project_id=project.id, environment_id=environment.id, event_type="lab_fault_clear_requested", aggregate_type="lab_fault", aggregate_id=str(fault.id), aggregate_version=fault.version, correlation_id=request.state.correlation_id, payload={"data": data})
    store_record(db, actor_user_id=auth.user.id, scope=scope, key=key, request_payload=body, response_status=202, response_body=response_body, resource_id=str(fault.id))
    db.commit()
    response.headers["ETag"] = etag(fault.version)
    publish_after_commit(db, project.id)
    return response_body


@router.get("/environments/{environment_id}/worker/status")
def worker_status(environment_id: uuid.UUID, request: Request, auth: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    require_environment(db, auth, environment_id)
    row = db.scalar(select(ControllerGeneration).where(ControllerGeneration.environment_id == environment_id).order_by(ControllerGeneration.generation.desc()).limit(1))
    return resource_envelope(request, {"status": row.status if row else "NOT_STARTED", "generation": row.generation if row else None, "worker_id": row.worker_id if row else None, "started_at": isoformat(row.started_at) if row else None, "last_heartbeat_at": isoformat(row.last_heartbeat_at) if row else None, "stale": (utc_now() - row.last_heartbeat_at).total_seconds() > LAB_POLICY.heartbeat_stale_seconds if row else True})
