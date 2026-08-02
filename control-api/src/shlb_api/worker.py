from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import uuid
from datetime import timedelta

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
    ObservationWindow,
    ObservedStateSnapshot,
    Project,
    ReintegrationRun,
    ReintegrationStage,
    RouteMembership,
    RoutingPolicy,
    VerificationResult,
)
from shlb_api.runtime import get_redis
from shlb_api.security import canonical_hash
from shlb_api.seed import IDS, INSTANCE_IDS, ROUTE_IDS
from shlb_api.worker_io import HAProxyRuntime, HAProxyRuntimeError, LabProbeClient, PrometheusEvidence
from shlb_api.worker_policy import INSTANCES, ROUTES, RuleDecision, classify, instance_capacity, route_instance_capacity


LOOP_SECONDS = 2.0
WINDOW_SECONDS = 12
WORKER_LOCK_ID = 0x53484C42
TERMINAL_ACTIONS = {"COMMITTED", "ROLLED_BACK", "ROLLBACK_FAILED", "FAILED", "NEEDS_REVIEW", "RESULT_UNKNOWN"}
TERMINAL_FAULTS = {"CLEARED", "EXPIRED", "FAILED"}
ACTIVE_INCIDENTS = {"OPEN", "MITIGATING", "VERIFYING", "RECOVERING", "NEEDS_REVIEW"}
STAGES = (("PROBING", None, 3), ("5%", 5, 2), ("20%", 20, 4), ("50%", 50, 6), ("100%", 100, 8), ("HEALTHY", 100, 1))


class ControlWorker:
    def __init__(self) -> None:
        self.worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.runtime = HAProxyRuntime(os.environ.get("SHLB_HAPROXY_RUNTIME_SOCKET", "/var/run/haproxy/haproxy.sock"))
        self.prometheus = PrometheusEvidence(os.environ.get("SHLB_PROMETHEUS_URL", "http://prometheus:9090"))
        self.probes = LabProbeClient(os.environ.get("SHLB_FAULT_TOKEN_FILE", "/run/secrets/fault_control_token"))
        self.sessions = get_session_factory()
        self.redis = get_redis()
        self.generation = 0
        self.generation_id: uuid.UUID | None = None
        self.lock_connection = None

    def start(self) -> None:
        self._acquire_authority()
        self._acquire_lease()
        self._start_generation()
        while True:
            started = time.monotonic()
            try:
                if not self._refresh_lease():
                    raise RuntimeError("worker coordination lease was lost")
                self.tick()
            except Exception as exc:  # bounded loop survives dependency interruptions
                print(json.dumps({"event": "worker_iteration_failed", "error_type": type(exc).__name__, "detail": str(exc)[:300]}, separators=(",", ":")), flush=True)
            elapsed = time.monotonic() - started
            time.sleep(max(0.1, LOOP_SECONDS - elapsed))

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
        if not self.redis.set("worker:authority:lease", self.worker_id, nx=True, ex=10):
            existing = self.redis.get("worker:authority:lease")
            if existing != self.worker_id:
                raise RuntimeError("another worker holds the Redis coordination lease")

    def _refresh_lease(self) -> bool:
        if self.redis.get("worker:authority:lease") != self.worker_id:
            return False
        self.redis.expire("worker:authority:lease", 10)
        return True

    def tick(self) -> None:
        with self.sessions() as db:
            generation = db.get(ControllerGeneration, self.generation_id)
            if generation is None or generation.status != "ACTIVE":
                raise RuntimeError("controller generation is no longer active")
            generation.last_heartbeat_at = utc_now()
            db.commit()

        self._process_fault_commands()
        window, snapshot, evidence, probes, memberships = self._observe()

        with self.sessions() as db:
            unfinished = db.scalar(select(Action).where(Action.environment_id == IDS["environment"], Action.lifecycle.in_(["PREPARED", "APPLIED", "STATE_CONFIRMED"])).order_by(Action.created_at).limit(1))
            if unfinished:
                self._recover_unfinished_action(db, unfinished)
                return
            action = db.scalar(select(Action).where(Action.environment_id == IDS["environment"], Action.lifecycle == "VERIFYING").order_by(Action.created_at).limit(1))
            if action:
                self._verify_action(db, action, window, evidence, memberships)
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
            decision = classify(evidence, probes, conflicts)
            if decision.final_class == "HEALTHY":
                if active_fault is None:
                    self._resolve_non_action_incidents(db)
                return
            if decision.final_class == "UNKNOWN" and active_fault is None:
                return
            if decision.final_class == "UNKNOWN" and active_fault and active_fault.scenario != "UNKNOWN_CONFLICT" and active_fault.applied_at and (utc_now() - active_fault.applied_at).total_seconds() < 20:
                return
            incident, certificate = self._persist_decision(db, window, decision)
            if decision.final_class == "ROUTE_INSTANCE_FAILURE" and decision.actionable:
                self._prepare_and_apply_route_action(db, incident, certificate, memberships)
            elif decision.final_class == "INSTANCE_DOWN" and decision.actionable:
                self._prepare_and_apply_instance_action(db, incident, certificate, memberships)

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
        if fault.scenario == "CHECKOUT_INST_B_FAILURE":
            return ["inst-b"], "route_failure", "checkout"
        if fault.scenario == "INST_B_DOWN":
            return ["inst-b"], "instance_down", None
        if fault.scenario == "SHARED_CHECKOUT_FAILURE":
            return list(INSTANCES), "route_failure", "checkout"
        return ["inst-b"], "unknown_conflict", "checkout"

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
                    fault.status = "FAILED"
                    fault.cleared_at = now
                    fault.version += 1
                    self._event(db, event_type="lab_fault_failed", aggregate_type="lab_fault", aggregate_id=fault.id, aggregate_version=fault.version, data={"error_type": type(exc).__name__})
            if faults:
                self._commit_publish(db)

    def _observe(self) -> tuple[ObservationWindow, ObservedStateSnapshot, dict, dict, list[dict]]:
        evidence = self.prometheus.collect(f"{WINDOW_SECONDS}s")
        probes = self.probes.probes()
        memberships = self.runtime.memberships()
        info = self.runtime.info()
        now = utc_now()
        available = sum(1 for value in evidence.values() if value["samples"] > 0)
        completeness = round(available / len(evidence), 3)
        total_samples = sum(value["samples"] for value in evidence.values())
        total_errors = sum(value["errors"] for value in evidence.values())
        capacities = {key: 100 for key in INSTANCES}
        route_capacity = {}
        for route in ROUTES:
            eligible = {item["server"].removeprefix("srv_").replace("_", "-") for item in memberships if item["backend"] == f"be_{route}" and item["admin_state"] == "ready" and item["weight"] > 0}
            route_capacity[route] = round(sum(capacities.get(instance, 0) for instance in eligible) / sum(capacities.values()) * 100, 1)
        metrics = {
            "summary": {
                "admitted_rps": round(total_samples / WINDOW_SECONDS, 1),
                "success_ratio": round((total_samples - total_errors) / total_samples, 4) if total_samples else None,
                "healthy_capacity_percent": min(route_capacity.values()) if route_capacity else None,
                "route_capacity_percent": route_capacity,
            },
            "memberships": evidence,
        }
        window = ObservationWindow(environment_id=IDS["environment"], started_at=now - timedelta(seconds=WINDOW_SECONDS), ended_at=now, completeness=completeness, metrics=metrics, probes=probes, freshness={"prometheus_seconds": 2, "runtime_seconds": 0, "probe_seconds": 0}, conflicts=[])
        snapshot = ObservedStateSnapshot(environment_id=IDS["environment"], action_id=None, source="HAPROXY_RUNTIME", process_id=info.get("Pid"), config_identifier=info.get("Config hash") or info.get("Release_date"), observed_at=now, memberships=memberships)
        with self.sessions() as db:
            db.add_all([window, snapshot])
            db.commit()
        return window, snapshot, evidence, probes, memberships

    def _persist_decision(self, db: Session, window: ObservationWindow, decision: RuleDecision) -> tuple[Incident, EvidenceCertificate]:
        route_id = ROUTE_IDS.get(decision.route) if decision.route else None
        instance_id = INSTANCE_IDS.get(decision.instance) if decision.instance else None
        canonical = f"class={decision.final_class}|route={decision.route or '-'}|instance={decision.instance or '-'}|schema=fingerprint-v1"
        fingerprint_hash = hashlib.sha256(canonical.encode()).hexdigest()
        incident = db.scalar(select(Incident).where(Incident.environment_id == IDS["environment"], Incident.fingerprint_hash == fingerprint_hash, Incident.status.in_(ACTIVE_INCIDENTS)).order_by(Incident.opened_at.desc()).limit(1))
        if incident:
            certificate = db.scalar(select(EvidenceCertificate).where(EvidenceCertificate.incident_id == incident.id).order_by(EvidenceCertificate.created_at.desc()).limit(1))
            if certificate is None:
                raise RuntimeError("active incident is missing its evidence certificate")
            return incident, certificate
        now = utc_now()
        summary_map = {
            "ROUTE_INSTANCE_FAILURE": "Checkout fails only on inst-b while peers and sibling routes remain healthy.",
            "SHARED_ROUTE_FAILURE": "Checkout fails across all physical instances; mass ejection is prohibited.",
            "INSTANCE_DOWN": "All registered routes on inst-b fail direct application probes.",
            "UNKNOWN": "Evidence is conflicting or incomplete; destructive action is prohibited.",
        }
        incident = Incident(environment_id=IDS["environment"], route_id=route_id, instance_id=instance_id, status="NEEDS_REVIEW" if decision.final_class == "UNKNOWN" else "OPEN", severity="CRITICAL" if decision.final_class in {"INSTANCE_DOWN", "SHARED_ROUTE_FAILURE"} else "WARNING", operational_class=decision.final_class, fingerprint_hash=fingerprint_hash, summary=summary_map[decision.final_class], opened_at=now, last_observed_at=now)
        db.add(incident)
        db.flush()
        fingerprint = Fingerprint(incident_id=incident.id, schema_version="fingerprint-v1", canonical_value=canonical, fingerprint_hash=fingerprint_hash)
        db.add(fingerprint)
        db.flush()
        classification = Classification(incident_id=incident.id, observation_window_id=window.id, revision=1, final_class=decision.final_class, confidence=decision.confidence, completeness=decision.completeness, evidence_support=decision.support, competing_hypotheses=decision.competing)
        db.add(classification)
        db.flush()
        safety = {"evaluated": False, "reason": "class is not actionable"}
        candidates = [{"unit": "NO_ACTION", "result": "selected", "reason": "UNKNOWN/shared scope cannot actuate"}]
        if decision.final_class == "ROUTE_INSTANCE_FAILURE":
            queues = {item["server"].removeprefix("srv_").replace("_", "-"): item["queue"] for item in self.runtime.memberships() if item["backend"] == "be_checkout"}
            safety = route_instance_capacity(capacities={key: 100 for key in INSTANCES}, target_instance="inst-b", queues=queues, minimum_reserve_percent=50)
            candidates = [
                {"unit": "ROUTE_INSTANCE", "targets": ["be_checkout/srv_inst_b"], "result": "selected" if safety["allowed"] else "rejected", "reason": "smallest supported scope" if safety["allowed"] else "capacity or queue guard failed"},
                {"unit": "INSTANCE", "targets": ["all inst-b memberships"], "result": "rejected", "reason": "healthy public/auth/catalog memberships would be displaced"},
                {"unit": "SHARED_ROUTE", "targets": ["all checkout memberships"], "result": "rejected", "reason": "checkout peers remain healthy"},
            ]
        elif decision.final_class == "INSTANCE_DOWN":
            current = self.runtime.memberships()
            route_peer_queues = {
                route: {
                    item["server"].removeprefix("srv_").replace("_", "-"): item["queue"]
                    for item in current
                    if item["backend"] == f"be_{route}" and item["server"] != "srv_inst_b"
                }
                for route in ROUTES
            }
            safety = instance_capacity(capacities={key: 100 for key in INSTANCES}, target_instance="inst-b", route_peer_queues=route_peer_queues, minimum_reserve_percent=50)
            candidates = [
                {"unit": "INSTANCE", "targets": [f"be_{route}/srv_inst_b" for route in ROUTES], "result": "selected" if safety["allowed"] else "rejected", "reason": "all routes and direct probes support instance scope" if safety["allowed"] else "physical reserve or peer queue guard failed"},
                {"unit": "ROUTE_INSTANCE", "result": "rejected", "reason": "failure spans all registered routes on inst-b"},
                {"unit": "SHARED_ROUTE", "result": "rejected", "reason": "healthy physical peers remain for every route"},
            ]
        certificate_payload = {"scope": decision.support, "safety": safety, "candidates": candidates, "window_id": str(window.id), "fingerprint": fingerprint_hash}
        certificate = EvidenceCertificate(incident_id=incident.id, observation_window_id=window.id, fingerprint_id=fingerprint.id, classification_id=classification.id, certificate_hash=canonical_hash(certificate_payload), scope_evidence=decision.support, safety_inputs=safety, candidate_actions=candidates)
        db.add(certificate)
        db.flush()
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
        membership = db.scalar(select(RouteMembership).where(RouteMembership.route_id == ROUTE_IDS["checkout"], RouteMembership.instance_id == INSTANCE_IDS["inst-b"]))
        if membership is None:
            raise RuntimeError("registered checkout/inst-b membership is missing")
        before = next(item for item in memberships if item["backend"] == membership.haproxy_backend and item["server"] == membership.haproxy_server)
        desired = db.scalar(select(DesiredRouteState).where(DesiredRouteState.membership_id == membership.id))
        if desired is None:
            raise RuntimeError("durable desired state is missing")
        now = utc_now()
        action = Action(environment_id=incident.environment_id, incident_id=incident.id, evidence_certificate_id=certificate.id, membership_id=membership.id, action_kind="ROUTE_MEMBERSHIP_QUARANTINE", lifecycle="PREPARED", controller_generation=self.generation, haproxy_backend=membership.haproxy_backend, haproxy_server=membership.haproxy_server, previous_desired={"admin_state": desired.admin_state, "weight": desired.weight}, previous_observed=before, requested_state={"admin_state": "drain", "weight": 0}, expected_effect="Remove only checkout/inst-b from eligible checkout selections while preserving inst-b public/auth/catalog.", preservation_set=["be_public/srv_inst_b", "be_auth/srv_inst_b", "be_catalog/srv_inst_b", "be_checkout/srv_inst_a", "be_checkout/srv_inst_c"], verification_criteria={"checkout_error_rate_max": 0.1, "minimum_real_samples": 12, "peer_queue_max": 5, "preserved_error_rate_max": 0.1}, rollback_strategy={"admin_state": desired.admin_state, "weight": desired.weight, "trigger": ["INEFFECTIVE", "HARMFUL", "READBACK_MISMATCH"]}, idempotency_key=f"controller-g{self.generation}:{incident.id}:checkout-inst-b", expires_at=now + timedelta(minutes=10))
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
        siblings_before = {(item["backend"], item["server"]): (item["admin_state"], item["weight"]) for item in memberships if item["server"] == "srv_inst_b" and item["backend"] != "be_checkout"}
        siblings_after = {(item["backend"], item["server"]): (item["admin_state"], item["weight"]) for item in after if item["server"] == "srv_inst_b" and item["backend"] != "be_checkout"}
        preserved = siblings_before == siblings_after
        confirmed = observed.get("admin_state") == "drain" and observed.get("weight") == 0 and preserved
        attempt.completed_at = utc_now()
        if confirmed and attempt.status == "ACKNOWLEDGED":
            attempt.status = "CONFIRMED"
        attempt.observed_state = {"target": observed, "inst_b_other_memberships_preserved": preserved, "siblings": {f"{backend}/{server}": {"admin_state": state[0], "weight": state[1]} for (backend, server), state in siblings_after.items()}}
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
        registered = db.scalars(select(RouteMembership).where(RouteMembership.instance_id == INSTANCE_IDS["inst-b"])).all()
        if len(registered) != len(ROUTES):
            raise RuntimeError("registered inst-b membership set is incomplete")
        targets = sorted((membership.haproxy_backend, membership.haproxy_server, membership.id) for membership in registered)
        before_by_target = {(item["backend"], item["server"]): item for item in memberships}
        if any((backend, server) not in before_by_target for backend, server, _ in targets):
            raise RuntimeError("HAProxy Runtime mapping changed before instance action")
        desired_rows = {
            row.membership_id: row
            for row in db.scalars(select(DesiredRouteState).where(DesiredRouteState.membership_id.in_([membership_id for _, _, membership_id in targets]))).all()
        }
        if len(desired_rows) != len(targets):
            raise RuntimeError("durable desired state is incomplete for inst-b")
        previous_desired = {
            f"{backend}/{server}": {"admin_state": desired_rows[membership_id].admin_state, "weight": desired_rows[membership_id].weight}
            for backend, server, membership_id in targets
        }
        previous_observed = {f"{backend}/{server}": before_by_target[(backend, server)] for backend, server, _ in targets}
        requested_targets = {f"{backend}/{server}": {"admin_state": "drain", "weight": 0} for backend, server, _ in targets}
        peers = sorted(f"{item['backend']}/{item['server']}" for item in memberships if item["server"] != "srv_inst_b")
        now = utc_now()
        representative = targets[0]
        action = Action(environment_id=incident.environment_id, incident_id=incident.id, evidence_certificate_id=certificate.id, membership_id=representative[2], action_kind="INSTANCE_QUARANTINE", lifecycle="PREPARED", controller_generation=self.generation, haproxy_backend="all_routes", haproxy_server="srv_inst_b", previous_desired={"targets": previous_desired}, previous_observed={"targets": previous_observed}, requested_state={"admin_state": "drain", "weight": 0, "targets": requested_targets}, expected_effect="Remove inst-b from every predeclared route while preserving physical peers inst-a and inst-c.", preservation_set=peers, verification_criteria={"all_routes_success_rate_min": 0.9, "minimum_real_samples_per_route": 6, "peer_queue_max": 5}, rollback_strategy={"targets": previous_desired, "trigger": ["INEFFECTIVE", "HARMFUL", "READBACK_MISMATCH"]}, idempotency_key=f"controller-g{self.generation}:{incident.id}:instance-inst-b", expires_at=now + timedelta(minutes=10))
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
        peers_before = {(item["backend"], item["server"]): (item["admin_state"], item["weight"]) for item in memberships if item["server"] != "srv_inst_b"}
        peers_after = {(item["backend"], item["server"]): (item["admin_state"], item["weight"]) for item in after if item["server"] != "srv_inst_b"}
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
                attempt.observed_state = {"target": observed, "inst_b_other_memberships_preserved": True, "siblings": siblings}
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
        checkout_members = [evidence[f"checkout/{instance}"] for instance in INSTANCES]
        affected_samples = sum(item["samples"] for item in checkout_members)
        affected_errors = sum(item["errors"] for item in checkout_members)
        affected_rate = affected_errors / affected_samples if affected_samples else None
        preserved = {route: evidence[f"{route}/inst-b"] for route in ("public", "auth", "catalog")}
        preservation_samples = sum(item["samples"] for item in preserved.values())
        preservation_ok = all(item["samples"] >= 3 and item["error_rate"] is not None and item["error_rate"] <= 0.1 for item in preserved.values())
        peer_queues = {item["server"]: item["queue"] for item in memberships if item["backend"] == "be_checkout" and item["server"] != "srv_inst_b"}
        queue_ok = all(value <= 5 for value in peer_queues.values())
        target = next((item for item in memberships if item["backend"] == action.haproxy_backend and item["server"] == action.haproxy_server), {})
        aligned = target.get("admin_state") == "drain" and target.get("weight") == 0
        affected_ok = affected_samples >= 12 and affected_rate is not None and affected_rate <= 0.1
        elapsed = (utc_now() - action.created_at).total_seconds()
        harmful = (not queue_ok and any(value > 10 for value in peer_queues.values())) or any(item["samples"] >= 3 and item["error_rate"] is not None and item["error_rate"] > 0.25 for item in preserved.values())
        if harmful:
            result = "HARMFUL"
        elif affected_ok and preservation_ok and queue_ok and aligned:
            result = "EFFECTIVE"
        elif elapsed >= 45 and affected_samples >= 12:
            result = "INEFFECTIVE"
        else:
            result = "INSUFFICIENT_EVIDENCE"
        revision = (db.scalar(select(func.max(VerificationResult.revision)).where(VerificationResult.action_id == action.id)) or 0) + 1
        verification = VerificationResult(action_id=action.id, revision=revision, result=result, affected_obligation={"passed": affected_ok, "error_rate": round(affected_rate, 4) if affected_rate is not None else None, "sample_count": affected_samples, "maximum_error_rate": 0.1}, preservation_obligation={"passed": preservation_ok and queue_ok and aligned, "routes": preserved, "peer_queues": peer_queues, "queue_limit": 5, "desired_observed_aligned": aligned, "retry_amplification": 1.0}, sample_count=affected_samples + preservation_samples, started_at=action.created_at, completed_at=utc_now() if result != "INSUFFICIENT_EVIDENCE" else None)
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
        for route in ROUTES:
            peers = [evidence[f"{route}/{instance}"] for instance in ("inst-a", "inst-c")]
            samples = sum(item["samples"] for item in peers)
            errors = sum(item["errors"] for item in peers)
            rate = errors / samples if samples else None
            route_results[route] = {"samples": samples, "errors": errors, "error_rate": round(rate, 4) if rate is not None else None, "passed": samples >= 6 and rate is not None and rate <= 0.1}
        target_rows = [item for item in memberships if item["server"] == "srv_inst_b"]
        peer_rows = [item for item in memberships if item["server"] != "srv_inst_b"]
        aligned = len(target_rows) == len(ROUTES) and all(item["admin_state"] == "drain" and item["weight"] == 0 for item in target_rows)
        queue_ok = all(item["queue"] <= 5 for item in peer_rows)
        affected_ok = all(result["passed"] for result in route_results.values())
        harmful = any(item["queue"] > 10 for item in peer_rows) or any(result["samples"] >= 3 and result["error_rate"] is not None and result["error_rate"] > 0.25 for result in route_results.values())
        elapsed = (utc_now() - action.created_at).total_seconds()
        if harmful:
            result = "HARMFUL"
        elif affected_ok and queue_ok and aligned:
            result = "EFFECTIVE"
        elif elapsed >= 45 and sum(item["samples"] for item in route_results.values()) >= 24:
            result = "INEFFECTIVE"
        else:
            result = "INSUFFICIENT_EVIDENCE"
        revision = (db.scalar(select(func.max(VerificationResult.revision)).where(VerificationResult.action_id == action.id)) or 0) + 1
        verification = VerificationResult(action_id=action.id, revision=revision, result=result, affected_obligation={"passed": affected_ok, "routes_after_instance_drain": route_results}, preservation_obligation={"passed": queue_ok and aligned, "physical_peers": [f"{item['backend']}/{item['server']}" for item in peer_rows], "peer_queue_max": max((item["queue"] for item in peer_rows), default=0), "all_inst_b_memberships_aligned": aligned, "capacity_counted_once": True}, sample_count=sum(item["samples"] for item in route_results.values()), started_at=action.created_at, completed_at=utc_now() if result != "INSUFFICIENT_EVIDENCE" else None)
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
        probe_ok = all(probes[f"{route}/inst-b"].get("application_ok") is True for route in ROUTES)
        latest = db.scalar(select(VerificationResult).where(VerificationResult.action_id == action.id).order_by(VerificationResult.revision.desc()).limit(1))
        previous_passes = int((latest.affected_obligation or {}).get("recovery_probe_passes", 0)) if latest else 0
        passes = previous_passes + 1 if probe_ok else 0
        if passes < 3:
            revision = (latest.revision if latest else 0) + 1
            verification = VerificationResult(action_id=action.id, revision=revision, result="INSUFFICIENT_EVIDENCE", affected_obligation={"recovery_probe_passes": passes, "required": 3, "all_inst_b_routes_healthy": probe_ok}, preservation_obligation={"quarantine_retained": True}, sample_count=passes, started_at=utc_now(), completed_at=None)
            db.add(verification)
            db.flush()
            self._event(db, event_type="verification_updated", aggregate_type="verification", aggregate_id=verification.id, aggregate_version=revision, incident_id=action.incident_id, action_id=action.id, data={"result": "INSUFFICIENT_EVIDENCE", "recovery_probe_passes": passes, "required": 3})
            self._commit_publish(db)
            return
        targets = action.rollback_strategy.get("targets", {})
        desired_rows = {str(row.membership_id): row for row in db.scalars(select(DesiredRouteState).where(DesiredRouteState.source_action_id == action.id)).all()}
        registered = db.scalars(select(RouteMembership).where(RouteMembership.instance_id == INSTANCE_IDS["inst-b"])).all()
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
            incident.status = "RESOLVED"
            incident.resolved_at = utc_now()
            incident.last_observed_at = incident.resolved_at
            incident.version += 1
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
        run = ReintegrationRun(environment_id=action.environment_id, incident_id=action.incident_id, action_id=action.id, status="ACTIVE", current_stage="PROBING", last_verified_stage="QUARANTINED", retry_count=0, maximum_retries=2, next_transition_at=now, started_at=now)
        db.add(run)
        db.flush()
        for sequence, (name, weight, minimum) in enumerate(STAGES):
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
        stage = db.scalar(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id, ReintegrationStage.status == "CURRENT").limit(1))
        if stage is None:
            self._recover_reintegration_transition(db, run, action)
            return
        now = utc_now()
        target_probe = probes["checkout/inst-b"]
        target_evidence = evidence["checkout/inst-b"]
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
                run.next_transition_at = now + timedelta(seconds=3)
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
                self._event(db, event_type="incident_resolved", aggregate_type="incident", aggregate_id=incident.id, aggregate_version=incident.version, incident_id=incident.id, action_id=action.id, data={"resolution": "verified staged reintegration", "final_weight": 100})
        else:
            stage.sample_count = target_evidence["samples"]
            stage.result = {"error_rate": target_evidence["error_rate"], "real_samples": target_evidence["samples"], "direct_probe": target_probe}
            elapsed = (now - stage.started_at).total_seconds() if stage.started_at else 0
            failed = target_probe.get("application_ok") is not True or (target_evidence["samples"] >= 2 and target_evidence["error_rate"] is not None and target_evidence["error_rate"] > 0.1)
            timed_out = elapsed > 45 and target_evidence["samples"] < stage.minimum_samples
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
                    run.next_transition_at = now + timedelta(seconds=3)
                run.version += 1
            elif elapsed >= 3 and target_evidence["samples"] >= stage.minimum_samples and target_evidence["error_rate"] is not None and target_evidence["error_rate"] <= 0.1:
                stage.status = "VERIFIED"
                stage.verified_at = now
                stage.observed_weight = self.runtime.read(action.haproxy_backend, action.haproxy_server)["weight"]
                run.last_verified_stage = stage.name
                next_stage = db.scalar(select(ReintegrationStage).where(ReintegrationStage.run_id == run.id, ReintegrationStage.sequence == stage.sequence + 1))
                if next_stage.name == "HEALTHY":
                    next_stage.observed_weight = 100
                else:
                    observed = self._set_reintegration_state(db, run, action, int(next_stage.requested_weight))
                    next_stage.observed_weight = observed["weight"]
                next_stage.status = "CURRENT"
                next_stage.started_at = now
                run.current_stage = next_stage.name
                run.next_transition_at = now + timedelta(seconds=3)
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
            run.next_transition_at = utc_now() + timedelta(seconds=3)
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
