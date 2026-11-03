from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from shlb_api.audit import add_outbox, append_audit, publish_pending_outbox
from shlb_api.contracts import utc_now
from shlb_api.database import get_engine, get_session_factory
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
    Project,
    ReintegrationRun,
    ReintegrationStage,
    RouteMembership,
    RouteGroup,
    RoutingPolicy,
    Service,
    VerificationResult,
)
from shlb_api.runtime import get_redis
from shlb_api.security import canonical_hash
from shlb_api.seed import IDS
from shlb_api.worker_io import HAProxyRuntime, HAProxyRuntimeError, LabProbeClient, PrometheusEvidence
from shlb_api.fastpath import FastPathController
from shlb_api.worker_policy import LAB_POLICY, RuleDecision, classify, instance_capacity, route_instance_capacity


WORKER_LOCK_ID = 0x53484C42
TERMINAL_ACTIONS = {"COMMITTED", "ROLLED_BACK", "ROLLBACK_FAILED", "FAILED", "NEEDS_REVIEW", "RESULT_UNKNOWN"}
TERMINAL_FAULTS = {"CLEARED", "EXPIRED", "FAILED"}
ACTIVE_INCIDENTS = {"OPEN", "MITIGATING", "VERIFYING", "RECOVERING", "NEEDS_REVIEW"}
WORKER_LEASE_KEY = "worker:authority:lease"
RECLAIM_LEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    redis.call("set", KEYS[1], ARGV[2], "EX", ARGV[3])
    return 1
end
return 0
"""
RENEW_LEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
end
return 0
"""


class ControlWorker:
    def __init__(self) -> None:
        self.worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.runtime = HAProxyRuntime(os.environ.get("SHLB_HAPROXY_RUNTIME_SOCKET", "/var/run/haproxy/admin.sock"))
        self.prometheus = PrometheusEvidence(os.environ.get("SHLB_PROMETHEUS_URL", "http://prometheus:9090"))
        self.probes = LabProbeClient(os.environ.get("SHLB_FAULT_TOKEN_FILE", "/run/secrets/fault_control_token"))
        self.sessions = get_session_factory()
        self.redis = get_redis()
        self.generation = 0
        self.generation_id: uuid.UUID | None = None
        self.lock_connection = None
        self.fastpath = FastPathController()
        self.routes: tuple[str, ...] = ()
        self.instances: tuple[str, ...] = ()
        # HYBRID_SHADOW: first-seen timestamp per "route/instance" key while the
        # fast-path controller has an active recommendation. Cleared the moment
        # the recommendation lapses. This is advisory telemetry only — it never
        # feeds HAProxy — and is what lets the benchmark data compare the shadow
        # signal's onset time against the deterministic rule engine's MTTD.
        self._fastpath_onset: dict[str, datetime] = {}
        self._authority_stop = threading.Event()
        self._authority_lost = threading.Event()

    def start(self) -> None:
        self._acquire_authority()
        self._acquire_lease()
        self._start_generation()
        threading.Thread(
            target=self._maintain_authority,
            name="worker-authority-heartbeat",
            daemon=True,
        ).start()
        while True:
            started = time.monotonic()
            try:
                if self._authority_lost.is_set() or not self._refresh_lease():
                    self._authority_lost.set()
                    raise RuntimeError("worker coordination lease was lost")
                self.tick()
            except Exception as exc:  # bounded loop survives dependency interruptions
                print(json.dumps({"event": "worker_iteration_failed", "error_type": type(exc).__name__, "detail": str(exc)[:300]}, separators=(",", ":")), flush=True)
                if self._authority_lost.is_set():
                    raise SystemExit(1) from exc
            elapsed = time.monotonic() - started
            time.sleep(max(0.1, LAB_POLICY.loop_seconds - elapsed))

    def _maintain_authority(self) -> None:
        interval = max(1.0, min(3.0, LAB_POLICY.worker_lease_seconds / 3))
        while not self._authority_stop.wait(interval):
            try:
                renewed = self.redis.eval(
                    RENEW_LEASE_SCRIPT,
                    1,
                    WORKER_LEASE_KEY,
                    self.worker_id,
                    str(LAB_POLICY.worker_lease_seconds),
                )
                if not renewed:
                    self._authority_lost.set()
                    print(json.dumps({"event": "worker_coordination_lease_lost"}), flush=True)
                    return
                with self.sessions() as db:
                    generation = db.get(ControllerGeneration, self.generation_id)
                    if generation is None or generation.status != "ACTIVE":
                        self._authority_lost.set()
                        print(json.dumps({"event": "worker_generation_lost"}), flush=True)
                        return
                    generation.last_heartbeat_at = utc_now()
                    db.commit()
            except Exception as exc:
                self._authority_lost.set()
                print(json.dumps({"event": "worker_authority_heartbeat_failed", "error_type": type(exc).__name__, "detail": str(exc)[:300]}, separators=(",", ":")), flush=True)
                return

    def _acquire_authority(self) -> None:
        self.lock_connection = get_engine().connect()
        acquired = self.lock_connection.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": WORKER_LOCK_ID}).scalar_one()
        if not acquired:
            raise RuntimeError("another control worker holds the PostgreSQL authority lock")
        if not os.path.exists(self.runtime.path):
            raise RuntimeError("HAProxy Runtime socket is not mounted into the worker")

    def _start_generation(self) -> None:
        now = utc_now()
        with self.sessions() as db:
            environment = db.get(Environment, IDS["environment"])
            if environment is None:
                raise RuntimeError("seeded LAB environment is unavailable")
            db.execute(select(type(environment).id).where(type(environment).id == environment.id).with_for_update())
            environment.controller_generation += 1
            self.generation = environment.controller_generation
            db.query(ControllerGeneration).filter(ControllerGeneration.environment_id == environment.id, ControllerGeneration.status == "ACTIVE").update({"status": "STALE", "stopped_at": now})
            generation = ControllerGeneration(environment_id=environment.id, generation=self.generation, worker_id=self.worker_id, status="ACTIVE", started_at=now, last_heartbeat_at=now)
            db.add(generation)
            db.commit()
            self.generation_id = generation.id

    def _acquire_lease(self) -> None:
        while True:
            if self.redis.set(WORKER_LEASE_KEY, self.worker_id, nx=True, ex=LAB_POLICY.worker_lease_seconds):
                return
            existing = self.redis.get(WORKER_LEASE_KEY)
            if existing == self.worker_id:
                self.redis.expire(WORKER_LEASE_KEY, LAB_POLICY.worker_lease_seconds)
                return
            if existing and self._lease_owner_is_stale(existing):
                reclaimed = self.redis.eval(
                    RECLAIM_LEASE_SCRIPT,
                    1,
                    WORKER_LEASE_KEY,
                    existing,
                    self.worker_id,
                    str(LAB_POLICY.worker_lease_seconds),
                )
                if reclaimed:
                    print(
                        json.dumps(
                            {"event": "worker_coordination_lease_reclaimed", "previous_owner": existing},
                            separators=(",", ":"),
                        ),
                        flush=True,
                    )
                    return
            time.sleep(max(0.5, LAB_POLICY.loop_seconds))

    def _lease_owner_is_stale(self, worker_id: str) -> bool:
        with self.sessions() as db:
            generation = db.scalar(
                select(ControllerGeneration)
                .where(
                    ControllerGeneration.environment_id == IDS["environment"],
                    ControllerGeneration.worker_id == worker_id,
                )
                .order_by(ControllerGeneration.generation.desc())
                .limit(1)
            )
            if generation is None:
                # start() holds the PostgreSQL advisory authority lock before
                # examining Redis. No registered generation can therefore be
                # an owner that is still allowed to mutate HAProxy.
                return True
            return generation.status != "ACTIVE" or generation.last_heartbeat_at < utc_now() - timedelta(
                seconds=LAB_POLICY.heartbeat_stale_seconds
            )

    def _refresh_lease(self) -> bool:
        return bool(self.redis.eval(
            RENEW_LEASE_SCRIPT,
            1,
            WORKER_LEASE_KEY,
            self.worker_id,
            str(LAB_POLICY.worker_lease_seconds),
        ))

    def tick(self) -> None:
        with self.sessions() as db:
            generation = db.get(ControllerGeneration, self.generation_id)
            if generation is None or generation.status != "ACTIVE":
                raise RuntimeError("controller generation is no longer active")
            generation.last_heartbeat_at = utc_now()
            db.commit()

        self.routes, self.instances = self._load_topology()
        if self._process_lab_reset_commands():
            return
        self._process_fault_commands()
        window, snapshot, evidence, probes, memberships, fast_recommendations = self._observe()

        with self.sessions() as db:
            latest_reset = db.scalar(
                select(LabResetRequest)
                .where(LabResetRequest.environment_id == IDS["environment"])
                .order_by(LabResetRequest.created_at.desc())
                .limit(1)
            )
            if latest_reset and latest_reset.status == "NEEDS_REVIEW":
                return
            unfinished = db.scalar(select(Action).where(Action.environment_id == IDS["environment"], Action.lifecycle.in_(["PREPARED", "APPLIED", "STATE_CONFIRMED"])).order_by(Action.created_at).limit(1))
            if unfinished:
                self._recover_unfinished_action(db, unfinished)
                return
            action = db.scalar(select(Action).where(Action.environment_id == IDS["environment"], Action.lifecycle == "VERIFYING").order_by(Action.created_at).limit(1))
            if action:
                self._verify_action(db, action, window, evidence, memberships)
                return
            unknown_instance_action = db.scalar(
                select(Action)
                .where(
                    Action.environment_id == IDS["environment"],
                    Action.lifecycle == "RESULT_UNKNOWN",
                    Action.action_kind == "INSTANCE_QUARANTINE",
                )
                .order_by(Action.created_at)
                .limit(1)
            )
            if unknown_instance_action:
                if self._faults_are_clear(db):
                    self._restore_instance_action(db, unknown_instance_action, probes)
                return
            recovery = db.scalar(select(ReintegrationRun).where(ReintegrationRun.environment_id == IDS["environment"], ReintegrationRun.status.in_(["ACTIVE", "ROLLING_BACK"])).order_by(ReintegrationRun.created_at).limit(1))
            if recovery:
                self._advance_reintegration(db, recovery, evidence, probes)
                return
            committed = db.scalar(select(Action).join(Incident, Incident.id == Action.incident_id).where(Action.environment_id == IDS["environment"], Action.lifecycle == "COMMITTED", Incident.status.in_(ACTIVE_INCIDENTS)).order_by(Action.created_at.desc()).limit(1))
            if committed and self._faults_are_clear(db):
                if committed.action_kind == "INSTANCE_QUARANTINE":
                    self._restore_instance_action(db, committed, probes)
                else:
                    self._start_reintegration(db, committed)
                return
            active_incident = db.scalar(select(Incident).where(Incident.environment_id == IDS["environment"], Incident.status.in_(ACTIVE_INCIDENTS), Incident.operational_class == "ROUTE_INSTANCE_FAILURE").order_by(Incident.opened_at.desc()).limit(1))
            if active_incident:
                return
            active_fault = db.scalar(select(LabFault).where(LabFault.environment_id == IDS["environment"], LabFault.status == "ACTIVE").order_by(LabFault.created_at.desc()).limit(1))
            conflicts = ["lab_ground_truth_conflicts_with_telemetry"] if active_fault and active_fault.scenario == "UNKNOWN_CONFLICT" else []
            decision = classify(evidence, probes, conflicts, statistical_support=fast_recommendations, routes=self.routes, instances=self.instances)
            if decision.final_class == "HEALTHY":
                if active_fault is None:
                    if self._incident_signal_confirmed(db, window, decision):
                        self._resolve_non_action_incidents(db)
                return
            if decision.final_class == "UNKNOWN" and active_fault is None:
                return
            if decision.final_class == "UNKNOWN" and active_fault and active_fault.scenario != "UNKNOWN_CONFLICT":
                target_routes = [active_fault.target_route] if active_fault.target_route else list(self.routes)
                target_instances = (
                    list(self.instances)
                    if active_fault.target_instance in (None, "all")
                    else [active_fault.target_instance]
                )
                target_sample_counts = [
                    evidence.get(f"{route}/{instance}", {}).get("samples", 0)
                    for route in target_routes
                    for instance in target_instances
                ]
                if not target_sample_counts or min(target_sample_counts) < LAB_POLICY.degraded_minimum_samples:
                    return
            needs_independent_confirmation = decision.final_class in {
                "ROUTE_INSTANCE_DEGRADED",
                "ROUTE_INSTANCE_FAILURE",
                "SHARED_ROUTE_FAILURE",
                "INSTANCE_DOWN",
            } or (
                decision.final_class == "UNKNOWN"
                and active_fault is not None
                and active_fault.scenario != "UNKNOWN_CONFLICT"
            )
            if needs_independent_confirmation and not self._incident_signal_confirmed(db, window, decision):
                return
            incident, certificate = self._persist_decision(db, window, decision)
            if decision.final_class == "ROUTE_INSTANCE_FAILURE" and decision.actionable:
                self._prepare_and_apply_route_action(db, incident, certificate, memberships)
            elif decision.final_class == "INSTANCE_DOWN" and decision.actionable:
                self._prepare_and_apply_instance_action(db, incident, certificate, memberships)

    def _incident_signal_confirmed(
        self,
        db: Session,
        window: ObservationWindow,
        decision: RuleDecision,
    ) -> bool:
        """Confirm an incident class in consecutive, independent windows."""
        cursor = window
        prior_windows: list[tuple[ObservationWindow, RuleDecision]] = []
        for _ in range(max(0, LAB_POLICY.incident_confirmation_windows - 1)):
            prior = db.scalar(
                select(ObservationWindow)
                .where(
                    ObservationWindow.environment_id == window.environment_id,
                    ObservationWindow.ended_at <= cursor.started_at,
                )
                .order_by(ObservationWindow.ended_at.desc())
                .limit(1)
            )
            if prior is None:
                return False
            gap = cursor.started_at - prior.ended_at
            if gap < timedelta(0) or gap > timedelta(seconds=LAB_POLICY.loop_seconds * 2):
                return False
            prior_decision = classify(
                prior.metrics.get("memberships", {}),
                prior.probes,
                prior.conflicts,
                routes=self.routes,
                instances=self.instances,
            )
            if (
                prior_decision.final_class != decision.final_class
                or prior_decision.route != decision.route
                or prior_decision.instance != decision.instance
                or (
                    decision.final_class == "UNKNOWN"
                    and prior_decision.support.get("reason") != decision.support.get("reason")
                )
            ):
                return False
            prior_windows.append((prior, prior_decision))
            cursor = prior
        decision.support["confirmation"] = {
            "required_windows": LAB_POLICY.incident_confirmation_windows,
            "windows": [
                {
                    "window_id": str(prior.id),
                    "started_at": prior.started_at.isoformat(),
                    "ended_at": prior.ended_at.isoformat(),
                    "final_class": prior_decision.final_class,
                    "route": prior_decision.route,
                    "instance": prior_decision.instance,
                    "metrics": prior.metrics,
                    "probes": prior.probes,
                    "conflicts": prior.conflicts,
                }
                for prior, prior_decision in reversed(prior_windows)
            ] + [{
                "window_id": str(window.id),
                "started_at": window.started_at.isoformat(),
                "ended_at": window.ended_at.isoformat(),
                "final_class": decision.final_class,
                "route": decision.route,
                "instance": decision.instance,
            }],
        }
        return True

    def _load_topology(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        with self.sessions() as db:
            routes = tuple(
                db.scalars(
                    select(RouteGroup.route_key)
                    .join(Service, RouteGroup.service_id == Service.id)
                    .where(Service.environment_id == IDS["environment"])
                    .order_by(RouteGroup.priority, RouteGroup.route_key)
                ).all()
            )
            instances = tuple(
                db.scalars(
                    select(BackendInstance.stable_name)
                    .join(Service, BackendInstance.service_id == Service.id)
                    .where(Service.environment_id == IDS["environment"], BackendInstance.status == "ACTIVE")
                    .order_by(BackendInstance.stable_name)
                ).all()
            )
        if not routes or not instances:
            raise RuntimeError("registered LAB topology is incomplete")
        return routes, instances

    def _resolve_non_action_incidents(self, db: Session) -> None:
        rows = db.scalars(select(Incident).where(Incident.environment_id == IDS["environment"], Incident.status.in_(ACTIVE_INCIDENTS))).all()
        changed = False
        for incident in rows:
            has_action = (db.scalar(select(func.count(Action.id)).where(Action.incident_id == incident.id)) or 0) > 0
            if has_action:
                continue
            incident.status = "RESOLVED"
            incident.resolved_at = utc_now()
            incident.last_observed_at = incident.resolved_at
            incident.version += 1
            self._event(db, event_type="incident_resolved", aggregate_type="incident", aggregate_id=incident.id, aggregate_version=incident.version, incident_id=incident.id, data={"resolution": "evidence returned to healthy bounds", "automatic_action": False})
            changed = True
        if changed:
            self._commit_publish(db)

    def _project(self, db: Session) -> Project:
        project = db.get(Project, IDS["project"])
        if project is None:
            raise RuntimeError("seeded project is unavailable")
        return project

    def _event(self, db: Session, *, event_type: str, aggregate_type: str, aggregate_id: uuid.UUID, aggregate_version: int, data: dict, incident_id: uuid.UUID | None = None, action_id: uuid.UUID | None = None) -> None:
        project = self._project(db)
        correlation = f"worker-g{self.generation}-{uuid.uuid4().hex[:12]}"
        append_audit(db, project=project, environment_id=IDS["environment"], actor_user_id=None, event_type=event_type.upper(), subject_type=aggregate_type, subject_id=str(aggregate_id), before=None, after=data, correlation_id=correlation)
        add_outbox(db, project_id=project.id, environment_id=IDS["environment"], event_type=event_type, aggregate_type=aggregate_type, aggregate_id=str(aggregate_id), aggregate_version=aggregate_version, correlation_id=correlation, payload={"incident_id": str(incident_id) if incident_id else None, "action_id": str(action_id) if action_id else None, "data": data})

    def _commit_publish(self, db: Session) -> None:
        db.commit()
        publish_pending_outbox(db, self.redis, project_id=IDS["project"])

    def _fault_targets(self, fault: LabFault) -> tuple[list[str], str, str | None]:
        if not fault.scenario_kind:
            raise RuntimeError(f"fault {fault.id} has no provisioned scenario kind")
        if fault.target_instance in (None, "all"):
            targets = list(self.instances)
        else:
            targets = [fault.target_instance]
        if fault.scenario_kind == "route_failure" and not fault.target_route:
            raise RuntimeError(f"fault {fault.id} has no route target")
        return targets, fault.scenario_kind, fault.target_route

    def _process_fault_commands(self) -> None:
        with self.sessions() as db:
            faults = db.scalars(select(LabFault).where(LabFault.environment_id == IDS["environment"], LabFault.status.in_(["REQUESTED", "ACTIVE", "CLEAR_REQUESTED"])).order_by(LabFault.created_at)).all()
            now = utc_now()
            for fault in faults:
                targets, kind, route = self._fault_targets(fault)
                try:
                    if fault.status == "REQUESTED":
                        for instance in targets:
                            self.probes.apply_fault(instance, {"kind": kind, "route": route, "expires_at": fault.expires_at.timestamp(), "ground_truth_id": fault.ground_truth_id})
                        fault.status = "ACTIVE"
                        fault.applied_at = now
                        fault.version += 1
                        self._event(db, event_type="lab_fault_applied", aggregate_type="lab_fault", aggregate_id=fault.id, aggregate_version=fault.version, data={"scenario": fault.scenario, "target_route": fault.target_route, "target_instance": fault.target_instance, "expires_at": fault.expires_at.isoformat()})
                    elif fault.status == "ACTIVE" and fault.expires_at > now:
                        # The target state is absolute and idempotent. Reassert it
                        # so a backend/worker restart cannot silently erase LAB
                        # ground truth while PostgreSQL still says it is active.
                        for instance in targets:
                            self.probes.apply_fault(instance, {"kind": kind, "route": route, "expires_at": fault.expires_at.timestamp(), "ground_truth_id": fault.ground_truth_id})
                    elif fault.status == "CLEAR_REQUESTED" or (fault.status == "ACTIVE" and fault.expires_at <= now):
                        for instance in targets:
                            self.probes.clear_fault(instance)
                        fault.status = "CLEARED" if fault.status == "CLEAR_REQUESTED" else "EXPIRED"
                        fault.cleared_at = now
                        fault.version += 1
                        self._event(db, event_type="lab_fault_cleared", aggregate_type="lab_fault", aggregate_id=fault.id, aggregate_version=fault.version, data={"status": fault.status, "ground_truth_id": fault.ground_truth_id})
                except Exception as exc:
                    cleanup_errors = []
                    for instance in targets:
                        try:
                            self.probes.clear_fault(instance)
                        except Exception as cleanup_exc:
                            cleanup_errors.append(type(cleanup_exc).__name__)
                    fault.status = "FAILED"
                    fault.cleared_at = now
                    fault.version += 1
                    self._event(db, event_type="lab_fault_failed", aggregate_type="lab_fault", aggregate_id=fault.id, aggregate_version=fault.version, data={"error_type": type(exc).__name__, "cleanup_error_types": cleanup_errors})
            if faults:
                self._commit_publish(db)

    def _process_lab_reset_commands(self) -> bool:
        """Restore the synthetic LAB to its registered baseline on operator request."""
        with self.sessions() as db:
            reset = db.scalar(
                select(LabResetRequest)
                .where(
                    LabResetRequest.environment_id == IDS["environment"],
                    LabResetRequest.status.in_(["REQUESTED", "RUNNING"]),
                )
                .order_by(LabResetRequest.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if reset is None:
                return False

            reset.status = "RUNNING"
            reset.version += 1
            reset.result = {"phase": "clearing_lab_faults"}
            self._event(db, event_type="lab_reset_started", aggregate_type="lab_reset", aggregate_id=reset.id, aggregate_version=reset.version, data=reset.result)
            self._commit_publish(db)

            clear_errors = []
            for instance in self.instances:
                try:
                    self.probes.clear_fault(instance)
                except Exception as exc:
                    clear_errors.append({"instance": instance, "error": type(exc).__name__})
            if clear_errors:
                reset.status = "NEEDS_REVIEW"
                reset.completed_at = utc_now()
                reset.result = {"phase": "clearing_lab_faults", "clear_errors": clear_errors}
                reset.version += 1
                self._event(db, event_type="lab_reset_needs_review", aggregate_type="lab_reset", aggregate_id=reset.id, aggregate_version=reset.version, data=reset.result)
                self._commit_publish(db)
                return True

            now = utc_now()
            faults = db.scalars(
                select(LabFault).where(
                    LabFault.environment_id == IDS["environment"],
                    LabFault.status.not_in(TERMINAL_FAULTS),
                )
            ).all()
            for fault in faults:
                fault.status = "CLEARED"
                fault.cleared_at = now
                fault.version += 1

            probes = self.probes.probes()
            failed_probes = {
                key: probe
                for key, probe in probes.items()
                if probe.get("application_ok") is not True
            }
            if failed_probes:
                reset.status = "NEEDS_REVIEW"
                reset.completed_at = now
                reset.result = {"phase": "health_gate", "failed_probes": failed_probes}
                reset.version += 1
                self._event(db, event_type="lab_reset_needs_review", aggregate_type="lab_reset", aggregate_id=reset.id, aggregate_version=reset.version, data=reset.result)
                self._commit_publish(db)
                return True

            rows = db.execute(
                select(RouteMembership, RouteGroup, BackendInstance, DesiredRouteState)
                .join(RouteGroup, RouteGroup.id == RouteMembership.route_id)
                .join(Service, Service.id == RouteGroup.service_id)
                .join(BackendInstance, BackendInstance.id == RouteMembership.instance_id)
                .outerjoin(DesiredRouteState, DesiredRouteState.membership_id == RouteMembership.id)
                .where(Service.environment_id == IDS["environment"])
                .order_by(RouteGroup.priority, BackendInstance.stable_name)
            ).all()
            if len(rows) != len(self.routes) * len(self.instances) or any(desired is None for _, _, _, desired in rows):
                reset.status = "NEEDS_REVIEW"
                reset.completed_at = now
                reset.result = {"phase": "topology_gate", "expected_memberships": len(self.routes) * len(self.instances), "found_memberships": len(rows)}
                reset.version += 1
                self._event(db, event_type="lab_reset_needs_review", aggregate_type="lab_reset", aggregate_id=reset.id, aggregate_version=reset.version, data=reset.result)
                self._commit_publish(db)
                return True

            baseline = []
            for membership, route, instance, desired in rows:
                desired.admin_state = "ready" if membership.baseline_weight > 0 else "drain"
                desired.weight = membership.baseline_weight
                desired.controller_generation = self.generation
                desired.source_action_id = None
                desired.version += 1
                baseline.append({
                    "backend": membership.haproxy_backend,
                    "server": membership.haproxy_server,
                    "admin_state": desired.admin_state,
                    "weight": desired.weight,
                    "route": route.route_key,
                    "instance": instance.stable_name,
                })
            reset.result = {"phase": "restoring_baseline", "membership_count": len(baseline)}
            reset.version += 1
            db.commit()

            readbacks = []
            runtime_errors = []
            for target in baseline:
                try:
                    observed = self.runtime.set_absolute(
                        target["backend"],
                        target["server"],
                        admin_state=target["admin_state"],
                        weight=target["weight"],
                    )["observed"]
                    readbacks.append({**target, "observed": observed})
                    if observed.get("admin_state") != target["admin_state"] or observed.get("weight") != target["weight"]:
                        runtime_errors.append({"target": target, "observed": observed})
                except Exception as exc:
                    runtime_errors.append({"target": target, "error": type(exc).__name__})

            now = utc_now()
            if runtime_errors:
                reset.status = "NEEDS_REVIEW"
                reset.completed_at = now
                reset.result = {"phase": "runtime_readback", "restored": readbacks, "errors": runtime_errors}
                reset.version += 1
                unfinished_actions = db.scalars(
                    select(Action).where(
                        Action.environment_id == IDS["environment"],
                        Action.lifecycle.in_(["PREPARED", "APPLIED", "STATE_CONFIRMED", "VERIFYING"]),
                    )
                ).all()
                for action in unfinished_actions:
                    action.lifecycle = "NEEDS_REVIEW"
                    action.terminal_at = now
                    action.version += 1
                for run in db.scalars(select(ReintegrationRun).where(ReintegrationRun.environment_id == IDS["environment"], ReintegrationRun.status.in_(["ACTIVE", "ROLLING_BACK"]))).all():
                    run.status = "NEEDS_REVIEW"
                    run.current_stage = "NEEDS_REVIEW"
                    run.completed_at = now
                    run.next_transition_at = None
                    run.version += 1
                self._event(db, event_type="lab_reset_needs_review", aggregate_type="lab_reset", aggregate_id=reset.id, aggregate_version=reset.version, data=reset.result)
                self._commit_publish(db)
                return True

            unfinished_actions = db.scalars(
                select(Action).where(
                    Action.environment_id == IDS["environment"],
                    Action.lifecycle.in_(["PREPARED", "APPLIED", "STATE_CONFIRMED", "VERIFYING"]),
                )
            ).all()
            for action in unfinished_actions:
                action.lifecycle = "ROLLED_BACK"
                action.terminal_at = now
                action.version += 1
            for run in db.scalars(select(ReintegrationRun).where(ReintegrationRun.environment_id == IDS["environment"], ReintegrationRun.status.in_(["ACTIVE", "ROLLING_BACK", "NEEDS_REVIEW"]))).all():
                run.status = "CANCELLED"
                run.current_stage = "CANCELLED"
                run.completed_at = now
                run.next_transition_at = None
                run.version += 1
                for stage in db.scalars(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id, ReintegrationStage.status.in_(["PENDING", "CURRENT"]))).all():
                    stage.status = "CANCELLED"
                    stage.result = {**stage.result, "cancelled_by": "LAB_BASELINE_RESET"}
            for incident in db.scalars(select(Incident).where(Incident.environment_id == IDS["environment"], Incident.status.in_(ACTIVE_INCIDENTS))).all():
                incident.status = "RESOLVED"
                incident.resolved_at = now
                incident.last_observed_at = now
                incident.version += 1
                self._event(db, event_type="incident_resolved", aggregate_type="incident", aggregate_id=incident.id, aggregate_version=incident.version, incident_id=incident.id, data={"resolution": "operator requested verified LAB baseline reset", "reset_request_id": str(reset.id)})

            reset.status = "COMPLETED"
            reset.completed_at = now
            reset.result = {"phase": "complete", "restored_memberships": len(readbacks), "readback_confirmed": True, "cleared_faults": len(faults)}
            reset.version += 1
            self.fastpath = FastPathController()
            self._event(db, event_type="lab_reset_completed", aggregate_type="lab_reset", aggregate_id=reset.id, aggregate_version=reset.version, data=reset.result)
            self._commit_publish(db)
            return True

    def _observe(self) -> tuple[ObservationWindow, ObservedStateSnapshot, dict, dict, list[dict], dict]:
        evidence = self.prometheus.collect(f"{LAB_POLICY.observation_window_seconds}s")
        probes = self.probes.probes()
        memberships = self.runtime.memberships()
        fast_samples = self.runtime.fast_samples()
        now = utc_now()
        fast_recommendations: dict[str, dict] = {}
        if LAB_POLICY.hybrid_shadow_enabled:
            for key, sample in fast_samples.items():
                route = key.split("/", 1)[0]
                route_active_capacity = sum(
                    1
                    for item in memberships
                    if item["backend"] == f"be_{route}"
                    and item["weight"] > 0
                    and item["admin_state"] == "ready"
                )
                observed_evidence = evidence.get(key, {})
                latency_ms = max(
                    sample["latency_ms"] or 0.0,
                    observed_evidence.get("p95_ms") or 0.0,
                )
                error_count = sample.get("errors_5xx_delta")
                request_count = sample.get("sessions_total_delta")
                error_rate = observed_evidence.get("error_rate")
                if error_rate is None:
                    error_rate = error_count / request_count if request_count else 0.0
                recommendation = self.fastpath.observe(
                    key,
                    latency_ms=latency_ms,
                    error_rate=error_rate,
                    active_capacity=route_active_capacity,
                    total_capacity=len(self.instances),
                )
                if recommendation is None:
                    self._fastpath_onset.pop(key, None)
                    continue
                onset = self._fastpath_onset.setdefault(key, now)
                fast_recommendations[key] = {
                    "recommended_weight": recommendation,
                    "flagged_since": onset.isoformat(),
                    "flagged_seconds": round((now - onset).total_seconds(), 1),
                }
        info = self.runtime.info()
        available = sum(1 for value in evidence.values() if value["samples"] > 0)
        completeness = round(available / len(evidence), 3)
        total_samples = sum(value["samples"] for value in evidence.values())
        total_errors = sum(value["errors"] for value in evidence.values())
        capacities = {key: 100 for key in self.instances}
        route_capacity = {}
        for route in self.routes:
            eligible = {item["server"].removeprefix("srv_").replace("_", "-") for item in memberships if item["backend"] == f"be_{route}" and item["admin_state"] == "ready" and item["weight"] > 0}
            route_capacity[route] = round(sum(capacities.get(instance, 0) for instance in eligible) / sum(capacities.values()) * 100, 1)
        metrics = {
            "summary": {
                "admitted_rps": round(total_samples / LAB_POLICY.observation_window_seconds, 1),
                "success_ratio": round((total_samples - total_errors) / total_samples, 4) if total_samples else None,
                "healthy_capacity_percent": min(route_capacity.values()) if route_capacity else None,
                "route_capacity_percent": route_capacity,
            },
            "memberships": evidence,
            "fast_path": fast_samples,
            "fast_path_recommendations": fast_recommendations,
        }
        window = ObservationWindow(environment_id=IDS["environment"], started_at=now - timedelta(seconds=LAB_POLICY.observation_window_seconds), ended_at=now, completeness=completeness, metrics=metrics, probes=probes, freshness={"prometheus_seconds": LAB_POLICY.loop_seconds, "runtime_seconds": 0, "probe_seconds": 0}, conflicts=[])
        snapshot = ObservedStateSnapshot(environment_id=IDS["environment"], action_id=None, source="HAPROXY_RUNTIME", process_id=info.get("Pid"), config_identifier=info.get("Config hash") or info.get("Release_date"), observed_at=now, memberships=memberships)
        with self.sessions() as db:
            db.add_all([window, snapshot])
            db.commit()
        return window, snapshot, evidence, probes, memberships, fast_recommendations

    def _persist_decision(self, db: Session, window: ObservationWindow, decision: RuleDecision) -> tuple[Incident, EvidenceCertificate]:
        window.conflicts = decision.support.get("conflicts", [])
        route_id = db.scalar(
            select(RouteGroup.id)
            .join(Service, RouteGroup.service_id == Service.id)
            .where(Service.environment_id == IDS["environment"], RouteGroup.route_key == decision.route)
        ) if decision.route else None
        instance_id = db.scalar(
            select(BackendInstance.id)
            .join(Service, BackendInstance.service_id == Service.id)
            .where(Service.environment_id == IDS["environment"], BackendInstance.stable_name == decision.instance)
        ) if decision.instance else None
        canonical = f"class={decision.final_class}|route={decision.route or '-'}|instance={decision.instance or '-'}|schema=fingerprint-v1"
        fingerprint_hash = hashlib.sha256(canonical.encode()).hexdigest()
        incident = db.scalar(select(Incident).where(Incident.environment_id == IDS["environment"], Incident.fingerprint_hash == fingerprint_hash, Incident.status.in_(ACTIVE_INCIDENTS)).order_by(Incident.opened_at.desc()).limit(1))
        route_instance_classes = {"ROUTE_INSTANCE_DEGRADED", "ROUTE_INSTANCE_FAILURE"}
        if (
            incident is None
            and decision.final_class in route_instance_classes
            and route_id is not None
            and instance_id is not None
        ):
            incident = db.scalar(
                select(Incident)
                .where(
                    Incident.environment_id == IDS["environment"],
                    Incident.route_id == route_id,
                    Incident.instance_id == instance_id,
                    Incident.operational_class.in_(route_instance_classes),
                    Incident.status.in_(ACTIVE_INCIDENTS),
                )
                .order_by(Incident.opened_at.desc())
                .limit(1)
            )
        now = utc_now()
        summary_map = {
            "ROUTE_INSTANCE_FAILURE": f"{decision.route} fails only on {decision.instance} while peers and sibling routes remain healthy.",
            "ROUTE_INSTANCE_DEGRADED": f"{decision.route} on {decision.instance} has elevated 5xx responses or a failing endpoint probe; evidence is not strong enough to quarantine it.",
            "SHARED_ROUTE_FAILURE": f"{decision.route} fails across all physical instances; mass ejection is prohibited.",
            "INSTANCE_DOWN": f"All registered routes on {decision.instance} fail direct application probes.",
            "UNKNOWN": "Evidence is conflicting or incomplete; destructive action is prohibited.",
        }
        is_new_incident = incident is None
        if incident is None:
            incident = Incident(environment_id=IDS["environment"], route_id=route_id, instance_id=instance_id, status="NEEDS_REVIEW" if decision.final_class == "UNKNOWN" else "OPEN", severity="CRITICAL" if decision.final_class in {"INSTANCE_DOWN", "SHARED_ROUTE_FAILURE"} else "WARNING", operational_class=decision.final_class, fingerprint_hash=fingerprint_hash, summary=summary_map[decision.final_class], opened_at=now, last_observed_at=now)
            db.add(incident)
            db.flush()
            revision = 1
        else:
            certificate = db.scalar(
                select(EvidenceCertificate)
                .where(EvidenceCertificate.incident_id == incident.id)
                .order_by(EvidenceCertificate.created_at.desc())
                .limit(1)
            )
            if certificate is None:
                raise RuntimeError("active incident is missing its evidence certificate")
            latest_window = db.get(ObservationWindow, certificate.observation_window_id)
            latest_classification = db.scalar(
                select(Classification)
                .where(Classification.incident_id == incident.id)
                .order_by(Classification.revision.desc())
                .limit(1)
            )
            if latest_window is None or latest_classification is None:
                raise RuntimeError("active incident is missing its classification history")
            if window.started_at < latest_window.ended_at:
                return incident, certificate
            revision = latest_classification.revision + 1
            if incident.operational_class != decision.final_class:
                incident.operational_class = decision.final_class
                incident.route_id = route_id
                incident.instance_id = instance_id
                incident.summary = summary_map[decision.final_class]
                incident.severity = "CRITICAL" if decision.final_class in {"INSTANCE_DOWN", "SHARED_ROUTE_FAILURE"} else "WARNING"
                incident.fingerprint_hash = fingerprint_hash
            incident.last_observed_at = now
            incident.version += 1
        fingerprint = Fingerprint(incident_id=incident.id, schema_version="fingerprint-v1", canonical_value=canonical, fingerprint_hash=fingerprint_hash)
        db.add(fingerprint)
        db.flush()
        classification = Classification(incident_id=incident.id, observation_window_id=window.id, revision=revision, final_class=decision.final_class, confidence=decision.confidence, completeness=decision.completeness, evidence_support=decision.support, competing_hypotheses=decision.competing)
        db.add(classification)
        db.flush()
        safety = {"evaluated": False, "reason": "class is not actionable"}
        no_action_reason = {
            "ROUTE_INSTANCE_DEGRADED": "Elevated 5xx or a failing probe was recorded, but isolation proof is insufficient to drain this route/backend safely.",
            "SHARED_ROUTE_FAILURE": "All route peers show a shared failure; mass ejection is unsafe, so retain traffic and require operator review.",
            "UNKNOWN": "Evidence is conflicting or incomplete; do not mutate HAProxy.",
        }.get(decision.final_class, "Class is non-actionable under the current safety policy.")
        candidates = [{"unit": "NO_ACTION", "result": "selected", "reason": no_action_reason}]
        if decision.final_class == "ROUTE_INSTANCE_FAILURE":
            queues = {item["server"].removeprefix("srv_").replace("_", "-"): item["queue"] for item in self.runtime.memberships() if item["backend"] == f"be_{decision.route}"}
            safety = route_instance_capacity(capacities={key: 100 for key in self.instances}, target_instance=decision.instance, queues=queues, minimum_reserve_percent=LAB_POLICY.minimum_physical_reserve_percent)
            candidates = [
                {"unit": "ROUTE_INSTANCE", "targets": [f"be_{decision.route}/srv_{decision.instance.replace('-', '_')}"], "result": "selected" if safety["allowed"] else "rejected", "reason": "smallest supported scope" if safety["allowed"] else "capacity or queue guard failed"},
                {"unit": "INSTANCE", "targets": [f"all {decision.instance} memberships"], "result": "rejected", "reason": f"healthy {', '.join(route for route in self.routes if route != decision.route)} memberships would be displaced"},
                {"unit": "SHARED_ROUTE", "targets": [f"all {decision.route} memberships"], "result": "rejected", "reason": f"{decision.route} peers remain healthy"},
            ]
        elif decision.final_class == "INSTANCE_DOWN":
            target_instance = decision.instance
            if target_instance is None:
                raise RuntimeError("instance-down decision has no target instance")
            target_server = f"srv_inst_{target_instance[-1]}"
            current = self.runtime.memberships()
            route_peer_queues = {
                route: {
                    item["server"].removeprefix("srv_").replace("_", "-"): item["queue"]
                    for item in current
                    if item["backend"] == f"be_{route}" and item["server"] != target_server
                }
                for route in self.routes
            }
            safety = instance_capacity(capacities={key: 100 for key in self.instances}, target_instance=target_instance, route_peer_queues=route_peer_queues, minimum_reserve_percent=LAB_POLICY.minimum_physical_reserve_percent)
            candidates = [
                {"unit": "INSTANCE", "targets": [f"be_{route}/{target_server}" for route in self.routes], "result": "selected" if safety["allowed"] else "rejected", "reason": "all routes and direct probes support instance scope" if safety["allowed"] else "physical reserve or peer queue guard failed"},
                {"unit": "ROUTE_INSTANCE", "result": "rejected", "reason": f"failure spans all registered routes on {target_instance}"},
                {"unit": "SHARED_ROUTE", "result": "rejected", "reason": "healthy physical peers remain for every route"},
            ]
        certificate_payload = {"scope": decision.support, "safety": safety, "candidates": candidates, "window_id": str(window.id), "fingerprint": fingerprint_hash}
        certificate = EvidenceCertificate(incident_id=incident.id, observation_window_id=window.id, fingerprint_id=fingerprint.id, classification_id=classification.id, certificate_hash=canonical_hash(certificate_payload), scope_evidence=decision.support, safety_inputs=safety, candidate_actions=candidates)
        db.add(certificate)
        db.flush()
        if is_new_incident:
            self._event(db, event_type="incident_detected", aggregate_type="incident", aggregate_id=incident.id, aggregate_version=incident.version, incident_id=incident.id, data={"classification": incident.operational_class, "summary": incident.summary})
        self._event(db, event_type="classification_completed", aggregate_type="classification", aggregate_id=classification.id, aggregate_version=classification.revision, incident_id=incident.id, data={"final_class": decision.final_class, "confidence": decision.confidence, "completeness": decision.completeness, "actionable": decision.actionable})
        self._commit_publish(db)
        return incident, certificate

    def _prepare_and_apply_route_action(self, db: Session, incident: Incident, certificate: EvidenceCertificate, memberships: list[dict]) -> None:
        if not certificate.safety_inputs.get("allowed"):
            incident.status = "NEEDS_REVIEW"
            db.commit()
            return
        existing = db.scalar(select(Action).where(Action.incident_id == incident.id).limit(1))
        if existing:
            return
        route_row = db.get(RouteGroup, incident.route_id) if incident.route_id else None
        instance_row = db.get(BackendInstance, incident.instance_id) if incident.instance_id else None
        if route_row is None or instance_row is None:
            raise RuntimeError("route-instance incident has an unknown registered scope")
        route = route_row.route_key
        instance = instance_row.stable_name
        membership = db.scalar(select(RouteMembership).where(RouteMembership.route_id == route_row.id, RouteMembership.instance_id == instance_row.id))
        if membership is None:
            raise RuntimeError(f"registered {route}/{instance} membership is missing")
        before = next(item for item in memberships if item["backend"] == membership.haproxy_backend and item["server"] == membership.haproxy_server)
        desired = db.scalar(select(DesiredRouteState).where(DesiredRouteState.membership_id == membership.id))
        if desired is None:
            raise RuntimeError("durable desired state is missing")
        now = utc_now()
        preserved_route_targets = [f"be_{other_route}/srv_{instance.replace('-', '_')}" for other_route in self.routes if other_route != route]
        preserved_peer_targets = [f"be_{route}/srv_{other_instance.replace('-', '_')}" for other_instance in self.instances if other_instance != instance]
        action = Action(environment_id=incident.environment_id, incident_id=incident.id, evidence_certificate_id=certificate.id, membership_id=membership.id, action_kind="ROUTE_MEMBERSHIP_QUARANTINE", lifecycle="PREPARED", controller_generation=self.generation, haproxy_backend=membership.haproxy_backend, haproxy_server=membership.haproxy_server, previous_desired={"admin_state": desired.admin_state, "weight": desired.weight}, previous_observed=before, requested_state={"admin_state": "drain", "weight": 0}, expected_effect=f"Remove only {route}/{instance} from eligible {route} selections while preserving other {instance} routes.", preservation_set=preserved_route_targets + preserved_peer_targets, verification_criteria={"route_error_rate_max": LAB_POLICY.healthy_rate, "minimum_real_samples": LAB_POLICY.route_verification_minimum_samples, "peer_queue_max": LAB_POLICY.peer_queue_limit, "preserved_error_rate_max": LAB_POLICY.healthy_rate}, rollback_strategy={"admin_state": desired.admin_state, "weight": desired.weight, "trigger": ["INEFFECTIVE", "HARMFUL", "READBACK_MISMATCH"]}, idempotency_key=f"controller-g{self.generation}:{incident.id}:{route}-{instance}", expires_at=now + timedelta(seconds=LAB_POLICY.action_expiry_seconds))
        db.add(action)
        db.flush()
        desired.admin_state = "drain"
        desired.weight = 0
        desired.controller_generation = self.generation
        desired.source_action_id = action.id
        desired.version += 1
        self._event(db, event_type="action_planned", aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=incident.id, action_id=action.id, data={"target": f"{membership.haproxy_backend}/{membership.haproxy_server}", "requested_state": action.requested_state, "safety": certificate.safety_inputs})
        self._commit_publish(db)

        attempt = ActionAttempt(action_id=action.id, sequence=1, operation="set_absolute_route_membership", status="ISSUED", command_hash=canonical_hash({"target": f"{membership.haproxy_backend}/{membership.haproxy_server}", "state": action.requested_state}), issued_at=utc_now(), response={}, observed_state={})
        db.add(attempt)
        db.commit()
        try:
            response = self.runtime.set_absolute(membership.haproxy_backend, membership.haproxy_server, admin_state="drain", weight=0)
            observed = response["observed"]
            attempt.response = response
            attempt.status = "ACKNOWLEDGED"
        except HAProxyRuntimeError as exc:
            try:
                observed = self.runtime.read(membership.haproxy_backend, membership.haproxy_server)
            except HAProxyRuntimeError:
                observed = {}
            if observed.get("admin_state") == "drain" and observed.get("weight") == 0:
                attempt.status = "ACKNOWLEDGEMENT_LOST_CONFIRMED"
                attempt.response = {"error_type": type(exc).__name__, "readback_recovered": True}
            else:
                attempt.status = "RESULT_UNKNOWN"
                attempt.error_code = "ACKNOWLEDGEMENT_LOST"
                attempt.response = {"error_type": type(exc).__name__, "readback_recovered": False}
                action.lifecycle = "RESULT_UNKNOWN"
                incident.status = "NEEDS_REVIEW"
                attempt.completed_at = utc_now()
                attempt.observed_state = observed
                self._event(db, event_type="drift_detected", aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=incident.id, action_id=action.id, data={"reason": "ambiguous Runtime result", "observed": observed})
                self._commit_publish(db)
                return
        after = self.runtime.memberships()
        siblings_before = {(item["backend"], item["server"]): (item["admin_state"], item["weight"]) for item in memberships if item["server"] == membership.haproxy_server and item["backend"] != membership.haproxy_backend}
        siblings_after = {(item["backend"], item["server"]): (item["admin_state"], item["weight"]) for item in after if item["server"] == membership.haproxy_server and item["backend"] != membership.haproxy_backend}
        preserved = siblings_before == siblings_after
        confirmed = observed.get("admin_state") == "drain" and observed.get("weight") == 0 and preserved
        attempt.completed_at = utc_now()
        if confirmed and attempt.status == "ACKNOWLEDGED":
            attempt.status = "CONFIRMED"
        attempt.observed_state = {"target": observed, "same_instance_other_routes_preserved": preserved, "siblings": {f"{backend}/{server}": {"admin_state": state[0], "weight": state[1]} for (backend, server), state in siblings_after.items()}}
        action.lifecycle = "VERIFYING" if confirmed else "NEEDS_REVIEW"
        action.version += 1
        incident.status = "VERIFYING" if confirmed else "NEEDS_REVIEW"
        incident.version += 1
        snapshot = ObservedStateSnapshot(environment_id=incident.environment_id, action_id=action.id, source="HAPROXY_RUNTIME", process_id=self.runtime.info().get("Pid"), config_identifier=self.runtime.info().get("Config hash") or self.runtime.info().get("Release_date"), observed_at=utc_now(), memberships=after)
        db.add(snapshot)
        event = "action_applied" if confirmed else "drift_detected"
        self._event(db, event_type=event, aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=incident.id, action_id=action.id, data={"lifecycle": action.lifecycle, "observed": observed, "preservation_confirmed": preserved})
        self._commit_publish(db)

    def _prepare_and_apply_instance_action(self, db: Session, incident: Incident, certificate: EvidenceCertificate, memberships: list[dict]) -> None:
        """Drain all predeclared memberships for one physical instance as one durable unit."""
        if not certificate.safety_inputs.get("allowed"):
            incident.status = "NEEDS_REVIEW"
            incident.version += 1
            self._commit_publish(db)
            return
        if db.scalar(select(Action).where(Action.incident_id == incident.id).limit(1)):
            return
        instance_row = db.get(BackendInstance, incident.instance_id) if incident.instance_id else None
        if instance_row is None:
            raise RuntimeError("instance-down incident has an unknown registered instance")
        instance = instance_row.stable_name
        target_server = f"srv_inst_{instance[-1]}"
        registered = db.scalars(select(RouteMembership).where(RouteMembership.instance_id == instance_row.id)).all()
        if len(registered) != len(self.routes):
            raise RuntimeError(f"registered {instance} membership set is incomplete")
        targets = sorted((membership.haproxy_backend, membership.haproxy_server, membership.id) for membership in registered)
        before_by_target = {(item["backend"], item["server"]): item for item in memberships}
        if any((backend, server) not in before_by_target for backend, server, _ in targets):
            raise RuntimeError("HAProxy Runtime mapping changed before instance action")
        desired_rows = {
            row.membership_id: row
            for row in db.scalars(select(DesiredRouteState).where(DesiredRouteState.membership_id.in_([membership_id for _, _, membership_id in targets]))).all()
        }
        if len(desired_rows) != len(targets):
            raise RuntimeError(f"durable desired state is incomplete for {instance}")
        previous_desired = {
            f"{backend}/{server}": {"admin_state": desired_rows[membership_id].admin_state, "weight": desired_rows[membership_id].weight}
            for backend, server, membership_id in targets
        }
        previous_observed = {f"{backend}/{server}": before_by_target[(backend, server)] for backend, server, _ in targets}
        requested_targets = {f"{backend}/{server}": {"admin_state": "drain", "weight": 0} for backend, server, _ in targets}
        peers = sorted(f"{item['backend']}/{item['server']}" for item in memberships if item["server"] != target_server)
        now = utc_now()
        representative = targets[0]
        action = Action(environment_id=incident.environment_id, incident_id=incident.id, evidence_certificate_id=certificate.id, membership_id=representative[2], action_kind="INSTANCE_QUARANTINE", lifecycle="PREPARED", controller_generation=self.generation, haproxy_backend="all_routes", haproxy_server=target_server, previous_desired={"targets": previous_desired}, previous_observed={"targets": previous_observed}, requested_state={"admin_state": "drain", "weight": 0, "targets": requested_targets}, expected_effect=f"Remove {instance} from every predeclared route while preserving physical peers {', '.join(other for other in self.instances if other != instance)}.", preservation_set=peers, verification_criteria={"all_routes_success_rate_min": 1 - LAB_POLICY.healthy_rate, "minimum_real_samples_per_route": LAB_POLICY.instance_route_minimum_samples, "peer_queue_max": LAB_POLICY.peer_queue_limit}, rollback_strategy={"targets": previous_desired, "trigger": ["INEFFECTIVE", "HARMFUL", "READBACK_MISMATCH"]}, idempotency_key=f"controller-g{self.generation}:{incident.id}:instance-{instance}", expires_at=now + timedelta(seconds=LAB_POLICY.action_expiry_seconds))
        db.add(action)
        db.flush()
        for _, _, membership_id in targets:
            desired = desired_rows[membership_id]
            desired.admin_state = "drain"
            desired.weight = 0
            desired.controller_generation = self.generation
            desired.source_action_id = action.id
            desired.version += 1
        self._event(db, event_type="action_planned", aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=incident.id, action_id=action.id, data={"targets": list(requested_targets), "requested_state": {"admin_state": "drain", "weight": 0}, "safety": certificate.safety_inputs})
        self._commit_publish(db)

        attempt = ActionAttempt(action_id=action.id, sequence=1, operation="set_absolute_instance_memberships", status="ISSUED", command_hash=canonical_hash(requested_targets), issued_at=utc_now(), response={}, observed_state={})
        db.add(attempt)
        db.commit()
        responses: dict[str, dict] = {}
        runtime_error: Exception | None = None
        for backend, server, _ in targets:
            try:
                responses[f"{backend}/{server}"] = self.runtime.set_absolute(backend, server, admin_state="drain", weight=0)
            except HAProxyRuntimeError as exc:
                runtime_error = exc
                break
        after = self.runtime.memberships()
        after_by_target = {(item["backend"], item["server"]): item for item in after}
        targets_confirmed = all(after_by_target.get((backend, server), {}).get("admin_state") == "drain" and after_by_target.get((backend, server), {}).get("weight") == 0 for backend, server, _ in targets)
        peers_before = {(item["backend"], item["server"]): (item["admin_state"], item["weight"]) for item in memberships if item["server"] != action.haproxy_server}
        peers_after = {(item["backend"], item["server"]): (item["admin_state"], item["weight"]) for item in after if item["server"] != action.haproxy_server}
        peers_preserved = peers_before == peers_after
        attempt.completed_at = utc_now()
        attempt.response = {"targets": responses, "error_type": type(runtime_error).__name__ if runtime_error else None}
        attempt.observed_state = {"targets": {f"{backend}/{server}": after_by_target.get((backend, server), {}) for backend, server, _ in targets}, "physical_peers_preserved": peers_preserved}
        if targets_confirmed and peers_preserved:
            attempt.status = "ACKNOWLEDGEMENT_LOST_CONFIRMED" if runtime_error else "CONFIRMED"
            action.lifecycle = "VERIFYING"
            incident.status = "VERIFYING"
            event_type = "action_applied"
        else:
            attempt.status = "RESULT_UNKNOWN"
            attempt.error_code = "ACKNOWLEDGEMENT_LOST" if runtime_error else "READBACK_MISMATCH"
            action.lifecycle = "RESULT_UNKNOWN"
            incident.status = "NEEDS_REVIEW"
            event_type = "drift_detected"
        action.version += 1
        incident.version += 1
        db.add(ObservedStateSnapshot(environment_id=incident.environment_id, action_id=action.id, source="HAPROXY_RUNTIME", process_id=self.runtime.info().get("Pid"), config_identifier=self.runtime.info().get("Config hash") or self.runtime.info().get("Release_date"), observed_at=utc_now(), memberships=after))
        self._event(db, event_type=event_type, aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=incident.id, action_id=action.id, data={"lifecycle": action.lifecycle, "targets_confirmed": targets_confirmed, "physical_peers_preserved": peers_preserved, "blind_retry": False})
        self._commit_publish(db)

    def _recover_unfinished_action(self, db: Session, action: Action) -> None:
        """Resolve a crash window from readback; never replay an ambiguous command."""
        if action.action_kind == "INSTANCE_QUARANTINE":
            current = self.runtime.memberships()
            current_by_target = {f"{item['backend']}/{item['server']}": item for item in current}
            targets = action.requested_state.get("targets", {})
            requested_matches = bool(targets) and all(
                current_by_target.get(target, {}).get("admin_state") == requested.get("admin_state")
                and current_by_target.get(target, {}).get("weight") == requested.get("weight")
                for target, requested in targets.items()
            )
            peers = [item for item in current if item["server"] != action.haproxy_server]
            peers_preserved = all(item["admin_state"] == "ready" and item["weight"] == 100 for item in peers)
            attempt = db.scalar(select(ActionAttempt).where(ActionAttempt.action_id == action.id).order_by(ActionAttempt.sequence.desc()).limit(1))
            incident = db.get(Incident, action.incident_id)
            if requested_matches and peers_preserved:
                action.lifecycle = "VERIFYING"
                incident.status = "VERIFYING"
                if attempt and attempt.status == "ISSUED":
                    attempt.status = "ACKNOWLEDGEMENT_LOST_CONFIRMED"
                    attempt.completed_at = utc_now()
                    attempt.response = {"restart_reconciliation": True, "blind_retry": False}
                    attempt.observed_state = {"targets": {target: current_by_target.get(target) for target in targets}, "physical_peers_preserved": True}
                event_type = "action_applied"
                data = {"lifecycle": "VERIFYING", "restart_reconciliation": True, "blind_retry": False, "targets_confirmed": True, "physical_peers_preserved": True}
            else:
                action.lifecycle = "RESULT_UNKNOWN"
                incident.status = "NEEDS_REVIEW"
                if attempt:
                    attempt.status = "RESULT_UNKNOWN"
                    attempt.completed_at = utc_now()
                    attempt.error_code = "RESTART_READBACK_MISMATCH"
                    attempt.observed_state = {"targets": {target: current_by_target.get(target) for target in targets}, "physical_peers_preserved": peers_preserved}
                event_type = "drift_detected"
                data = {"reason": "unfinished instance action did not match requested readback after restart", "blind_retry": False, "targets_confirmed": requested_matches, "physical_peers_preserved": peers_preserved}
            action.version += 1
            incident.version += 1
            db.add(ObservedStateSnapshot(environment_id=action.environment_id, action_id=action.id, source="HAPROXY_RUNTIME", process_id=self.runtime.info().get("Pid"), config_identifier=self.runtime.info().get("Config hash") or self.runtime.info().get("Release_date"), observed_at=utc_now(), memberships=current))
            self._event(db, event_type=event_type, aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=incident.id, action_id=action.id, data=data)
            self._commit_publish(db)
            return
        observed = self.runtime.read(action.haproxy_backend, action.haproxy_server)
        siblings = [item for item in self.runtime.memberships() if item["server"] == action.haproxy_server and item["backend"] != action.haproxy_backend]
        preserved = all(item["admin_state"] == "ready" and item["weight"] == 100 for item in siblings)
        requested_matches = observed.get("admin_state") == action.requested_state.get("admin_state") and observed.get("weight") == action.requested_state.get("weight")
        attempt = db.scalar(select(ActionAttempt).where(ActionAttempt.action_id == action.id).order_by(ActionAttempt.sequence.desc()).limit(1))
        incident = db.get(Incident, action.incident_id)
        if requested_matches and preserved:
            action.lifecycle = "VERIFYING"
            incident.status = "VERIFYING"
            if attempt and attempt.status == "ISSUED":
                attempt.status = "ACKNOWLEDGEMENT_LOST_CONFIRMED"
                attempt.completed_at = utc_now()
                attempt.response = {"restart_reconciliation": True, "blind_retry": False}
                attempt.observed_state = {"target": observed, "target_instance_other_memberships_preserved": True, "siblings": siblings}
            event_type = "action_applied"
            data = {"lifecycle": "VERIFYING", "restart_reconciliation": True, "blind_retry": False, "observed": observed, "preservation_confirmed": True}
        else:
            action.lifecycle = "RESULT_UNKNOWN"
            incident.status = "NEEDS_REVIEW"
            if attempt:
                attempt.status = "RESULT_UNKNOWN"
                attempt.completed_at = utc_now()
                attempt.error_code = "RESTART_READBACK_MISMATCH"
                attempt.observed_state = {"target": observed, "siblings": siblings}
            event_type = "drift_detected"
            data = {"reason": "unfinished action did not match requested readback after restart", "blind_retry": False, "observed": observed, "preservation_confirmed": preserved}
        action.version += 1
        incident.version += 1
        db.add(ObservedStateSnapshot(environment_id=action.environment_id, action_id=action.id, source="HAPROXY_RUNTIME", process_id=self.runtime.info().get("Pid"), config_identifier=self.runtime.info().get("Release_date"), observed_at=utc_now(), memberships=self.runtime.memberships()))
        self._event(db, event_type=event_type, aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=incident.id, action_id=action.id, data=data)
        self._commit_publish(db)

    def _verify_action(self, db: Session, action: Action, window: ObservationWindow, evidence: dict, memberships: list[dict]) -> None:
        if action.action_kind == "INSTANCE_QUARANTINE":
            self._verify_instance_action(db, action, evidence, memberships)
            return
        route = action.haproxy_backend.removeprefix("be_")
        instance = action.haproxy_server.removeprefix("srv_").replace("_", "-")
        route_members = [evidence[f"{route}/{member_instance}"] for member_instance in self.instances]
        affected_samples = sum(item["samples"] for item in route_members)
        affected_errors = sum(item["errors"] for item in route_members)
        affected_rate = affected_errors / affected_samples if affected_samples else None
        preserved = {other_route: evidence[f"{other_route}/{instance}"] for other_route in self.routes if other_route != route}
        preservation_samples = sum(item["samples"] for item in preserved.values())
        preservation_ok = all(item["samples"] >= LAB_POLICY.control_minimum_samples and item["error_rate"] is not None and item["error_rate"] <= LAB_POLICY.healthy_rate for item in preserved.values())
        peer_queues = {item["server"]: item["queue"] for item in memberships if item["backend"] == action.haproxy_backend and item["server"] != action.haproxy_server}
        queue_ok = all(value <= LAB_POLICY.peer_queue_limit for value in peer_queues.values())
        target = next((item for item in memberships if item["backend"] == action.haproxy_backend and item["server"] == action.haproxy_server), {})
        aligned = target.get("admin_state") == "drain" and target.get("weight") == 0
        affected_ok = affected_samples >= LAB_POLICY.route_verification_minimum_samples and affected_rate is not None and affected_rate <= LAB_POLICY.healthy_rate
        elapsed = (utc_now() - action.created_at).total_seconds()
        harmful = (not queue_ok and any(value > LAB_POLICY.harmful_queue_limit for value in peer_queues.values())) or any(item["samples"] >= LAB_POLICY.control_minimum_samples and item["error_rate"] is not None and item["error_rate"] > LAB_POLICY.harmful_error_rate for item in preserved.values())
        if harmful:
            result = "HARMFUL"
        elif affected_ok and preservation_ok and queue_ok and aligned:
            result = "EFFECTIVE"
        elif elapsed >= LAB_POLICY.verification_timeout_seconds and affected_samples >= LAB_POLICY.route_verification_minimum_samples:
            result = "INEFFECTIVE"
        else:
            result = "INSUFFICIENT_EVIDENCE"
        revision = (db.scalar(select(func.max(VerificationResult.revision)).where(VerificationResult.action_id == action.id)) or 0) + 1
        verification = VerificationResult(action_id=action.id, revision=revision, result=result, affected_obligation={"passed": affected_ok, "error_rate": round(affected_rate, 4) if affected_rate is not None else None, "sample_count": affected_samples, "maximum_error_rate": LAB_POLICY.healthy_rate}, preservation_obligation={"passed": preservation_ok and queue_ok and aligned, "routes": preserved, "peer_queues": peer_queues, "queue_limit": LAB_POLICY.peer_queue_limit, "desired_observed_aligned": aligned, "retry_amplification": 1.0}, sample_count=affected_samples + preservation_samples, started_at=action.created_at, completed_at=utc_now() if result != "INSUFFICIENT_EVIDENCE" else None)
        db.add(verification)
        db.flush()
        if result == "EFFECTIVE":
            action.lifecycle = "COMMITTED"
            action.terminal_at = utc_now()
            action.version += 1
            incident = db.get(Incident, action.incident_id)
            incident.status = "MITIGATING"
            incident.version += 1
        elif result in {"HARMFUL", "INEFFECTIVE"}:
            self.runtime.set_absolute(action.haproxy_backend, action.haproxy_server, admin_state=action.rollback_strategy["admin_state"], weight=int(action.rollback_strategy["weight"]))
            action.lifecycle = "ROLLED_BACK"
            action.terminal_at = utc_now()
            action.version += 1
            incident = db.get(Incident, action.incident_id)
            incident.status = "NEEDS_REVIEW"
            incident.version += 1
            self._event(db, event_type="rollback_started", aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=action.incident_id, action_id=action.id, data={"verification_result": result, "rollback_state": action.rollback_strategy})
        self._event(db, event_type="verification_updated", aggregate_type="verification", aggregate_id=verification.id, aggregate_version=revision, incident_id=action.incident_id, action_id=action.id, data={"result": result, "affected": verification.affected_obligation, "preservation": verification.preservation_obligation, "action_lifecycle": action.lifecycle})
        self._commit_publish(db)

    def _verify_instance_action(self, db: Session, action: Action, evidence: dict, memberships: list[dict]) -> None:
        route_results: dict[str, dict] = {}
        for route in self.routes:
            target_instance = action.haproxy_server.removeprefix("srv_").replace("_", "-")
            peers = [evidence[f"{route}/{instance}"] for instance in self.instances if instance != target_instance]
            samples = sum(item["samples"] for item in peers)
            errors = sum(item["errors"] for item in peers)
            rate = errors / samples if samples else None
            route_results[route] = {"samples": samples, "errors": errors, "error_rate": round(rate, 4) if rate is not None else None, "passed": samples >= LAB_POLICY.instance_route_minimum_samples and rate is not None and rate <= LAB_POLICY.healthy_rate}
        target_rows = [item for item in memberships if item["server"] == action.haproxy_server]
        peer_rows = [item for item in memberships if item["server"] != action.haproxy_server]
        aligned = len(target_rows) == len(self.routes) and all(item["admin_state"] == "drain" and item["weight"] == 0 for item in target_rows)
        queue_ok = all(item["queue"] <= LAB_POLICY.peer_queue_limit for item in peer_rows)
        affected_ok = all(result["passed"] for result in route_results.values())
        harmful = any(item["queue"] > LAB_POLICY.harmful_queue_limit for item in peer_rows) or any(result["samples"] >= LAB_POLICY.control_minimum_samples and result["error_rate"] is not None and result["error_rate"] > LAB_POLICY.harmful_error_rate for result in route_results.values())
        elapsed = (utc_now() - action.created_at).total_seconds()
        if harmful:
            result = "HARMFUL"
        elif affected_ok and queue_ok and aligned:
            result = "EFFECTIVE"
        elif elapsed >= LAB_POLICY.verification_timeout_seconds and sum(item["samples"] for item in route_results.values()) >= LAB_POLICY.instance_route_minimum_samples * len(self.routes):
            result = "INEFFECTIVE"
        else:
            result = "INSUFFICIENT_EVIDENCE"
        revision = (db.scalar(select(func.max(VerificationResult.revision)).where(VerificationResult.action_id == action.id)) or 0) + 1
        verification = VerificationResult(action_id=action.id, revision=revision, result=result, affected_obligation={"passed": affected_ok, "routes_after_instance_drain": route_results}, preservation_obligation={"passed": queue_ok and aligned, "physical_peers": [f"{item['backend']}/{item['server']}" for item in peer_rows], "peer_queue_max": max((item["queue"] for item in peer_rows), default=0), "all_target_instance_memberships_aligned": aligned, "capacity_counted_once": True}, sample_count=sum(item["samples"] for item in route_results.values()), started_at=action.created_at, completed_at=utc_now() if result != "INSUFFICIENT_EVIDENCE" else None)
        db.add(verification)
        db.flush()
        incident = db.get(Incident, action.incident_id)
        if result == "EFFECTIVE":
            action.lifecycle = "COMMITTED"
            action.terminal_at = utc_now()
            action.version += 1
            incident.status = "MITIGATING"
            incident.version += 1
        elif result in {"HARMFUL", "INEFFECTIVE"}:
            rollback_ok, observed = self._apply_instance_states(action.rollback_strategy.get("targets", {}))
            action.lifecycle = "ROLLED_BACK" if rollback_ok else "ROLLBACK_FAILED"
            action.terminal_at = utc_now()
            action.version += 1
            incident.status = "NEEDS_REVIEW"
            incident.version += 1
            self._event(db, event_type="rollback_started", aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=action.incident_id, action_id=action.id, data={"verification_result": result, "rollback_confirmed": rollback_ok, "observed": observed})
        self._event(db, event_type="verification_updated", aggregate_type="verification", aggregate_id=verification.id, aggregate_version=revision, incident_id=action.incident_id, action_id=action.id, data={"result": result, "affected": verification.affected_obligation, "preservation": verification.preservation_obligation, "action_lifecycle": action.lifecycle})
        self._commit_publish(db)

    def _apply_instance_states(self, targets: dict) -> tuple[bool, dict]:
        runtime_error = False
        for target, state in targets.items():
            backend, separator, server = target.partition("/")
            if not separator:
                runtime_error = True
                continue
            try:
                self.runtime.set_absolute(backend, server, admin_state=str(state["admin_state"]), weight=int(state["weight"]))
            except (HAProxyRuntimeError, KeyError, TypeError, ValueError):
                runtime_error = True
                break
        current = {f"{item['backend']}/{item['server']}": item for item in self.runtime.memberships()}
        matches = bool(targets) and all(current.get(target, {}).get("admin_state") == state.get("admin_state") and current.get(target, {}).get("weight") == state.get("weight") for target, state in targets.items())
        return matches, {target: current.get(target, {}) for target in targets}

    def _restore_instance_action(self, db: Session, action: Action, probes: dict) -> None:
        target_instance = action.haproxy_server.removeprefix("srv_").replace("_", "-")
        probe_ok = all(probes[f"{route}/{target_instance}"].get("application_ok") is True for route in self.routes)
        latest = db.scalar(select(VerificationResult).where(VerificationResult.action_id == action.id).order_by(VerificationResult.revision.desc()).limit(1))
        previous_passes = int((latest.affected_obligation or {}).get("recovery_probe_passes", 0)) if latest else 0
        passes = previous_passes + 1 if probe_ok else 0
        if passes < LAB_POLICY.instance_recovery_probe_passes:
            revision = (latest.revision if latest else 0) + 1
            verification = VerificationResult(action_id=action.id, revision=revision, result="INSUFFICIENT_EVIDENCE", affected_obligation={"recovery_probe_passes": passes, "required": LAB_POLICY.instance_recovery_probe_passes, "all_target_instance_routes_healthy": probe_ok}, preservation_obligation={"quarantine_retained": True}, sample_count=passes, started_at=utc_now(), completed_at=None)
            db.add(verification)
            db.flush()
            self._event(db, event_type="verification_updated", aggregate_type="verification", aggregate_id=verification.id, aggregate_version=revision, incident_id=action.incident_id, action_id=action.id, data={"result": "INSUFFICIENT_EVIDENCE", "recovery_probe_passes": passes, "required": LAB_POLICY.instance_recovery_probe_passes})
            self._commit_publish(db)
            return
        targets = action.rollback_strategy.get("targets", {})
        desired_rows = {str(row.membership_id): row for row in db.scalars(select(DesiredRouteState).where(DesiredRouteState.source_action_id == action.id)).all()}
        membership = db.get(RouteMembership, action.membership_id)
        if membership is None:
            raise RuntimeError("instance recovery membership is missing")
        registered = db.scalars(select(RouteMembership).where(RouteMembership.instance_id == membership.instance_id)).all()
        membership_by_target = {f"{row.haproxy_backend}/{row.haproxy_server}": row for row in registered}
        for target, state in targets.items():
            membership = membership_by_target.get(target)
            desired = desired_rows.get(str(membership.id)) if membership else None
            if desired is None:
                raise RuntimeError("cannot restore an unregistered instance membership")
            desired.admin_state = str(state["admin_state"])
            desired.weight = int(state["weight"])
            desired.controller_generation = self.generation
            desired.version += 1
        sequence = (db.scalar(select(func.max(ActionAttempt.sequence)).where(ActionAttempt.action_id == action.id)) or 0) + 1
        attempt = ActionAttempt(action_id=action.id, sequence=sequence, operation="restore_instance_after_probe_gate", status="ISSUED", command_hash=canonical_hash(targets), issued_at=utc_now(), response={"probe_passes": passes}, observed_state={})
        db.add(attempt)
        db.commit()
        confirmed, observed = self._apply_instance_states(targets)
        attempt.completed_at = utc_now()
        attempt.observed_state = {"targets": observed}
        db.add(ObservedStateSnapshot(environment_id=action.environment_id, action_id=action.id, source="HAPROXY_RUNTIME", process_id=self.runtime.info().get("Pid"), config_identifier=self.runtime.info().get("Config hash") or self.runtime.info().get("Release_date"), observed_at=utc_now(), memberships=self.runtime.memberships()))
        incident = db.get(Incident, action.incident_id)
        if confirmed:
            attempt.status = "CONFIRMED"
            action.lifecycle = "COMMITTED"
            action.terminal_at = utc_now()
            action.version += 1
            incident.status = "RESOLVED"
            incident.resolved_at = utc_now()
            incident.last_observed_at = incident.resolved_at
            incident.version += 1
            revision = (db.scalar(select(func.max(VerificationResult.revision)).where(VerificationResult.action_id == action.id)) or 0) + 1
            verification = VerificationResult(
                action_id=action.id,
                revision=revision,
                result="EFFECTIVE",
                affected_obligation={"recovery_probe_passes": passes, "required": LAB_POLICY.instance_recovery_probe_passes, "all_target_instance_routes_healthy": probe_ok},
                preservation_obligation={"all_original_instance_memberships_restored": True, "runtime_readback_confirmed": True},
                sample_count=passes,
                started_at=action.created_at,
                completed_at=utc_now(),
            )
            db.add(verification)
            db.flush()
            self._event(db, event_type="verification_updated", aggregate_type="verification", aggregate_id=verification.id, aggregate_version=revision, incident_id=incident.id, action_id=action.id, data={"result": verification.result, "recovery_probe_passes": passes, "restored_targets": list(targets)})
            self._event(db, event_type="incident_resolved", aggregate_type="incident", aggregate_id=incident.id, aggregate_version=incident.version, incident_id=incident.id, action_id=action.id, data={"resolution": "instance probe gate and Runtime restore confirmed", "restored_targets": list(targets)})
        else:
            attempt.status = "RESULT_UNKNOWN"
            attempt.error_code = "RESTORE_READBACK_MISMATCH"
            action.lifecycle = "RESULT_UNKNOWN"
            action.version += 1
            incident.status = "NEEDS_REVIEW"
            incident.version += 1
            self._event(db, event_type="drift_detected", aggregate_type="action", aggregate_id=action.id, aggregate_version=action.version, incident_id=incident.id, action_id=action.id, data={"reason": "instance restore did not match Runtime readback", "observed": observed, "blind_retry": False})
        self._commit_publish(db)

    @staticmethod
    def _faults_are_clear(db: Session) -> bool:
        return (db.scalar(select(func.count(LabFault.id)).where(LabFault.environment_id == IDS["environment"], LabFault.status.not_in(TERMINAL_FAULTS))) or 0) == 0

    def _start_reintegration(self, db: Session, action: Action) -> None:
        existing = db.scalar(select(ReintegrationRun).where(ReintegrationRun.action_id == action.id).limit(1))
        if existing:
            return
        now = utc_now()
        run = ReintegrationRun(environment_id=action.environment_id, incident_id=action.incident_id, action_id=action.id, status="ACTIVE", current_stage="PROBING", last_verified_stage="QUARANTINED", retry_count=0, maximum_retries=LAB_POLICY.maximum_reintegration_retries, next_transition_at=now, started_at=now)
        db.add(run)
        db.flush()
        for sequence, (name, weight, minimum) in enumerate(LAB_POLICY.reintegration_stages):
            db.add(ReintegrationStage(run_id=run.id, sequence=sequence, name=name, requested_weight=weight, observed_weight=0 if name == "PROBING" else None, status="CURRENT" if name == "PROBING" else "PENDING", sample_count=0, minimum_samples=minimum, started_at=now if name == "PROBING" else None, result={}))
        incident = db.get(Incident, action.incident_id)
        incident.status = "RECOVERING"
        incident.version += 1
        self._event(db, event_type="reintegration_progress", aggregate_type="reintegration", aggregate_id=run.id, aggregate_version=run.version, incident_id=run.incident_id, action_id=run.action_id, data={"status": run.status, "stage": "PROBING", "last_verified_stage": "QUARANTINED"})
        self._commit_publish(db)

    def _set_reintegration_state(self, db: Session, run: ReintegrationRun, action: Action, weight: int) -> dict:
        desired = db.scalar(select(DesiredRouteState).where(DesiredRouteState.membership_id == action.membership_id))
        desired.admin_state = "ready" if weight > 0 else "drain"
        desired.weight = weight
        desired.controller_generation = self.generation
        desired.source_action_id = action.id
        desired.version += 1
        db.commit()
        return self.runtime.set_absolute(action.haproxy_backend, action.haproxy_server, admin_state="ready" if weight > 0 else "drain", weight=weight)["observed"]

    def _advance_reintegration(self, db: Session, run: ReintegrationRun, evidence: dict, probes: dict) -> None:
        action = db.get(Action, run.action_id)
        membership = db.get(RouteMembership, action.membership_id)
        if membership is None:
            raise RuntimeError("reintegration membership is missing its seed baseline")
        stage = db.scalar(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id, ReintegrationStage.status == "CURRENT").limit(1))
        if stage is None:
            self._recover_reintegration_transition(db, run, action)
            return
        now = utc_now()
        target_key = (
            f"{action.haproxy_backend.removeprefix('be_')}/"
            f"{action.haproxy_server.removeprefix('srv_').replace('_', '-')}"
        )
        target_probe = probes[target_key]
        target_evidence = evidence[target_key]
        if stage.requested_weight is not None:
            observed = self.runtime.read(action.haproxy_backend, action.haproxy_server)
            expected_admin = "ready" if stage.requested_weight > 0 else "drain"
            if observed.get("admin_state") != expected_admin or observed.get("weight") != stage.requested_weight:
                run.status = "NEEDS_REVIEW"
                run.current_stage = "NEEDS_REVIEW"
                run.version += 1
                incident = db.get(Incident, run.incident_id)
                incident.status = "NEEDS_REVIEW"
                incident.version += 1
                self._event(db, event_type="drift_detected", aggregate_type="reintegration", aggregate_id=run.id, aggregate_version=run.version, incident_id=run.incident_id, action_id=run.action_id, data={"reason": "reintegration desired state differs from Runtime readback", "stage": stage.name, "expected": {"admin_state": expected_admin, "weight": stage.requested_weight}, "observed": observed})
                self._commit_publish(db)
                return
        if stage.name == "PROBING":
            stage.sample_count = stage.sample_count + 1 if target_probe.get("application_ok") is True else 0
            stage.result = {"direct_probe": target_probe, "consecutive_passes": stage.sample_count}
            if stage.sample_count >= stage.minimum_samples:
                stage.status = "VERIFIED"
                stage.verified_at = now
                run.last_verified_stage = "PROBING"
                next_stage = db.scalar(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id, ReintegrationStage.sequence == stage.sequence + 1))
                observed = self._set_reintegration_state(db, run, action, int(next_stage.requested_weight))
                next_stage.status = "CURRENT"
                next_stage.started_at = now
                next_stage.observed_weight = observed["weight"]
                run.current_stage = next_stage.name
                run.next_transition_at = now + timedelta(seconds=LAB_POLICY.reintegration_cooldown_seconds)
                run.version += 1
        elif stage.name == "HEALTHY":
            if target_probe.get("application_ok") is True:
                stage.sample_count += 1
            if stage.sample_count >= stage.minimum_samples:
                stage.status = "VERIFIED"
                stage.verified_at = now
                run.status = "COMPLETED"
                run.current_stage = "HEALTHY"
                run.last_verified_stage = "HEALTHY"
                run.completed_at = now
                run.next_transition_at = None
                run.version += 1
                incident = db.get(Incident, run.incident_id)
                incident.status = "RESOLVED"
                incident.resolved_at = now
                incident.last_observed_at = now
                incident.version += 1
                self._event(db, event_type="incident_resolved", aggregate_type="incident", aggregate_id=incident.id, aggregate_version=incident.version, incident_id=incident.id, action_id=action.id, data={"resolution": "verified staged reintegration", "final_weight": membership.baseline_weight})
        else:
            stage.sample_count = target_evidence["samples"]
            stage.result = {"error_rate": target_evidence["error_rate"], "real_samples": target_evidence["samples"], "direct_probe": target_probe}
            elapsed = (now - stage.started_at).total_seconds() if stage.started_at else 0
            failed = target_probe.get("application_ok") is not True or (target_evidence["samples"] >= 2 and target_evidence["error_rate"] is not None and target_evidence["error_rate"] > LAB_POLICY.healthy_rate)
            timed_out = elapsed > LAB_POLICY.reintegration_stage_timeout_seconds and target_evidence["samples"] < stage.minimum_samples
            if failed or timed_out:
                run.retry_count += 1
                stage.status = "FAILED"
                stage.result["reason"] = "health regression" if failed else "insufficient real samples"
                fallback_weight = 0 if run.last_verified_stage in {"QUARANTINED", "PROBING"} else int(run.last_verified_stage.rstrip("%"))
                self._set_reintegration_state(db, run, action, fallback_weight)
                if run.retry_count > run.maximum_retries:
                    run.status = "NEEDS_REVIEW"
                    run.current_stage = "NEEDS_REVIEW"
                    incident = db.get(Incident, run.incident_id)
                    incident.status = "NEEDS_REVIEW"
                    incident.version += 1
                else:
                    probe_stage = db.scalar(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id, ReintegrationStage.sequence == 0))
                    probe_stage.status = "CURRENT"
                    probe_stage.sample_count = 0
                    probe_stage.started_at = now
                    probe_stage.verified_at = None
                    run.current_stage = "PROBING"
                    run.last_verified_stage = "QUARANTINED" if fallback_weight == 0 else run.last_verified_stage
                    run.next_transition_at = now + timedelta(seconds=LAB_POLICY.reintegration_cooldown_seconds)
                run.version += 1
            elif elapsed >= LAB_POLICY.reintegration_cooldown_seconds and target_evidence["samples"] >= stage.minimum_samples and target_evidence["error_rate"] is not None and target_evidence["error_rate"] <= LAB_POLICY.healthy_rate:
                stage.status = "VERIFIED"
                stage.verified_at = now
                stage.observed_weight = self.runtime.read(action.haproxy_backend, action.haproxy_server)["weight"]
                run.last_verified_stage = stage.name
                next_stage = db.scalar(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id, ReintegrationStage.sequence == stage.sequence + 1))
                if next_stage.name == "HEALTHY":
                    observed = self._set_reintegration_state(db, run, action, membership.baseline_weight)
                    next_stage.observed_weight = observed["weight"]
                else:
                    observed = self._set_reintegration_state(db, run, action, int(next_stage.requested_weight))
                    next_stage.observed_weight = observed["weight"]
                next_stage.status = "CURRENT"
                next_stage.started_at = now
                run.current_stage = next_stage.name
                run.next_transition_at = now + timedelta(seconds=LAB_POLICY.reintegration_cooldown_seconds)
                run.version += 1
        self._event(db, event_type="reintegration_progress", aggregate_type="reintegration", aggregate_id=run.id, aggregate_version=run.version, incident_id=run.incident_id, action_id=run.action_id, data={"status": run.status, "stage": run.current_stage, "last_verified_stage": run.last_verified_stage, "retry_count": run.retry_count, "observed_weight": stage.observed_weight, "sample_count": stage.sample_count, "minimum_samples": stage.minimum_samples})
        self._commit_publish(db)

    def _recover_reintegration_transition(self, db: Session, run: ReintegrationRun, action: Action) -> None:
        """Resolve a commit-before-Runtime crash window by readback, never command replay."""
        desired = db.scalar(select(DesiredRouteState).where(DesiredRouteState.membership_id == action.membership_id))
        observed = self.runtime.read(action.haproxy_backend, action.haproxy_server)
        expected_admin = desired.admin_state if desired else None
        expected_weight = desired.weight if desired else None
        pending = db.scalars(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id, ReintegrationStage.status == "PENDING").order_by(ReintegrationStage.sequence)).all()
        matching = next((item for item in pending if item.requested_weight == expected_weight), None)
        matches = desired is not None and observed.get("admin_state") == expected_admin and observed.get("weight") == expected_weight
        if matches and matching is not None:
            matching.status = "CURRENT"
            matching.started_at = utc_now()
            matching.observed_weight = observed.get("weight")
            run.current_stage = matching.name
            run.next_transition_at = utc_now() + timedelta(seconds=LAB_POLICY.reintegration_cooldown_seconds)
            run.version += 1
            self._event(db, event_type="reintegration_progress", aggregate_type="reintegration", aggregate_id=run.id, aggregate_version=run.version, incident_id=run.incident_id, action_id=run.action_id, data={"status": run.status, "stage": matching.name, "restart_reconciliation": True, "blind_retry": False, "observed_weight": observed.get("weight")})
        else:
            run.status = "NEEDS_REVIEW"
            run.current_stage = "NEEDS_REVIEW"
            run.version += 1
            incident = db.get(Incident, run.incident_id)
            incident.status = "NEEDS_REVIEW"
            incident.version += 1
            self._event(db, event_type="drift_detected", aggregate_type="reintegration", aggregate_id=run.id, aggregate_version=run.version, incident_id=run.incident_id, action_id=run.action_id, data={"reason": "unfinished reintegration transition is ambiguous", "restart_reconciliation": True, "blind_retry": False, "desired": {"admin_state": expected_admin, "weight": expected_weight}, "observed": observed})
        self._commit_publish(db)


def main() -> None:
    ControlWorker().start()


if __name__ == "__main__":
    main()
