from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from shlb_api.audit import add_outbox, append_audit, publish_pending_outbox
from shlb_api.database import get_session_factory
from shlb_api.models import (
    AuditEvent,
    BackendInstance,
    DeploymentVersion,
    DesiredRouteState,
    Environment,
    Project,
    RetryPolicy,
    RouteGroup,
    RouteMembership,
    RoutingPolicy,
    Service,
    Team,
    TeamMembership,
    User,
)
from shlb_api.runtime import get_redis
from shlb_api.security import encrypt_field, hash_password
from shlb_api.settings import get_settings


IDS = {
    "user": uuid.UUID("10000000-0000-4000-8000-000000000001"),
    "researcher": uuid.UUID("10000000-0000-4000-8000-000000000002"),
    "team": uuid.UUID("20000000-0000-4000-8000-000000000001"),
    "project": uuid.UUID("30000000-0000-4000-8000-000000000001"),
    "environment": uuid.UUID("40000000-0000-4000-8000-000000000001"),
    "service": uuid.UUID("50000000-0000-4000-8000-000000000001"),
    "version": uuid.UUID("60000000-0000-4000-8000-000000000001"),
    "version_v2": uuid.UUID("60000000-0000-4000-8000-000000000002"),
    "foreign_team": uuid.UUID("20000000-0000-4000-8000-000000000099"),
    "foreign_project": uuid.UUID("30000000-0000-4000-8000-000000000099"),
    "routing_policy": uuid.UUID("90000000-0000-4000-8000-000000000001"),
}

INSTANCE_IDS = {
    "inst-a": uuid.UUID("70000000-0000-4000-8000-000000000001"),
    "inst-b": uuid.UUID("70000000-0000-4000-8000-000000000002"),
    "inst-c": uuid.UUID("70000000-0000-4000-8000-000000000003"),
    "inst-d": uuid.UUID("70000000-0000-4000-8000-000000000004"),
}
V1_INSTANCES = ("inst-a", "inst-b")
V2_INSTANCES = ("inst-c", "inst-d")

ROUTE_IDS = {
    "public": uuid.UUID("80000000-0000-4000-8000-000000000001"),
    "auth": uuid.UUID("80000000-0000-4000-8000-000000000002"),
    "catalog": uuid.UUID("80000000-0000-4000-8000-000000000003"),
    "checkout": uuid.UUID("80000000-0000-4000-8000-000000000004"),
}


def membership_id(route_index: int, instance_index: int) -> uuid.UUID:
    return uuid.UUID(f"a0000000-0000-4000-8000-{route_index:04d}{instance_index:08d}")


def retry_policy_id(route_index: int) -> uuid.UUID:
    return uuid.UUID(f"b0000000-0000-4000-8000-{route_index:012d}")


def seed() -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    with session_factory() as db:
        user = db.get(User, IDS["user"])
        if user is None:
            user = User(
                id=IDS["user"],
                email_normalized=settings.bootstrap_email,
                password_hash=hash_password(settings.bootstrap_password),
                status="ACTIVE",
            )
            db.add(user)

        researcher = db.get(User, IDS["researcher"])
        if researcher is None:
            researcher = User(
                id=IDS["researcher"],
                email_normalized="researcher@shlb.local",
                password_hash=hash_password(settings.bootstrap_password),
                status="ACTIVE",
            )
            db.add(researcher)

        team = db.get(Team, IDS["team"])
        if team is None:
            team = Team(id=IDS["team"], name="Local reliability team", slug="local-reliability")
            db.add(team)

        foreign_team = db.get(Team, IDS["foreign_team"])
        if foreign_team is None:
            foreign_team = Team(
                id=IDS["foreign_team"],
                name="Isolated verification team",
                slug="isolated-verification",
            )
            db.add(foreign_team)
        db.flush()

        membership = db.scalar(
            select(TeamMembership).where(
                TeamMembership.team_id == team.id,
                TeamMembership.user_id == user.id,
            )
        )
        if membership is None:
            db.add(
                TeamMembership(
                    team_id=team.id,
                    user_id=user.id,
                    role="PROJECT_ADMIN",
                )
            )

        researcher_membership = db.scalar(
            select(TeamMembership).where(
                TeamMembership.team_id == team.id,
                TeamMembership.user_id == researcher.id,
            )
        )
        if researcher_membership is None:
            db.add(
                TeamMembership(
                    team_id=team.id,
                    user_id=researcher.id,
                    role="RESEARCHER",
                )
            )

        project = db.get(Project, IDS["project"])
        if project is None:
            project = Project(
                id=IDS["project"],
                team_id=team.id,
                name="Self Healing Load Balancer",
                slug="self-healing-load-balancer",
                status="ACTIVE",
            )
            db.add(project)

        if db.get(Project, IDS["foreign_project"]) is None:
            db.add(
                Project(
                    id=IDS["foreign_project"],
                    team_id=foreign_team.id,
                    name="Scope isolation fixture",
                    slug="scope-isolation-fixture",
                    status="ACTIVE",
                )
            )
        db.flush()

        environment = db.get(Environment, IDS["environment"])
        if environment is None:
            environment = Environment(
                id=IDS["environment"],
                project_id=project.id,
                name="Local traffic lab",
                kind="LAB",
                mode="RULES_ONLY",
                timezone="Asia/Kolkata",
                automation_frozen=False,
                controller_generation=0,
            )
            db.add(environment)
        else:
            environment.mode = "RULES_ONLY"
        db.flush()

        service = db.get(Service, IDS["service"])
        if service is None:
            service = Service(
                id=IDS["service"],
                environment_id=environment.id,
                name="demo-application",
                protocol="HTTP",
                status="ACTIVE",
            )
            db.add(service)
        db.flush()

        deployment = db.get(DeploymentVersion, IDS["version"])
        if deployment is None:
            deployment = DeploymentVersion(
                id=IDS["version"],
                service_id=service.id,
                version_label="demo-v1",
                artifact_digest="sha256:phase1-demo-v1",
                deployed_at=datetime(2026, 7, 26, tzinfo=UTC),
                status="ACTIVE",
            )
            db.add(deployment)
        db.flush()

        deployment_v2 = db.get(DeploymentVersion, IDS["version_v2"])
        if deployment_v2 is None:
            deployment_v2 = DeploymentVersion(
                id=IDS["version_v2"],
                service_id=service.id,
                version_label="demo-v2",
                artifact_digest="sha256:phase1-demo-v2",
                deployed_at=datetime(2026, 9, 6, tzinfo=UTC),
                status="ACTIVE",
            )
            db.add(deployment_v2)
        db.flush()

        version_by_instance = {name: deployment.id for name in V1_INSTANCES} | {name: deployment_v2.id for name in V2_INSTANCES}
        for stable_name, instance_id in INSTANCE_IDS.items():
            backend = db.get(BackendInstance, instance_id)
            if backend is None:
                docker_name = f"demo-backend-{stable_name[-1]}"
                backend = BackendInstance(
                    id=instance_id,
                    service_id=service.id,
                    version_id=version_by_instance[stable_name],
                    stable_name=stable_name,
                    address_ciphertext=encrypt_field(docker_name),
                    port=8080,
                    capacity=100,
                    probe_profile="phase1-http-healthz",
                    status="ACTIVE",
                )
                db.add(backend)
            else:
                backend.version_id = version_by_instance[stable_name]

        route_specs = {
            "public": (10, "STANDARD"),
            "auth": (20, "HIGH"),
            "catalog": (30, "STANDARD"),
            "checkout": (40, "CRITICAL"),
        }
        for route_key, (priority, criticality) in route_specs.items():
            if db.get(RouteGroup, ROUTE_IDS[route_key]) is None:
                db.add(
                    RouteGroup(
                        id=ROUTE_IDS[route_key],
                        service_id=service.id,
                        route_key=route_key,
                        match_type="PREFIX",
                        match_value=f"/{route_key}",
                        priority=priority,
                        criticality=criticality,
                        default_behavior="FAIL_CLOSED",
                    )
                )
        db.flush()

        for route_index, route_key in enumerate(route_specs, start=1):
            for instance_index, stable_name in enumerate(INSTANCE_IDS, start=1):
                identifier = membership_id(route_index, instance_index)
                membership = db.get(RouteMembership, identifier)
                if membership is None:
                    db.add(
                        RouteMembership(
                            id=identifier,
                            route_id=ROUTE_IDS[route_key],
                            instance_id=INSTANCE_IDS[stable_name],
                            haproxy_backend=f"be_{route_key}",
                            haproxy_server=f"srv_inst_{stable_name[-1]}",
                            version_id=version_by_instance[stable_name],
                            baseline_weight=100,
                            baseline_maxconn=None,
                            status="ACTIVE",
                        )
                    )
                else:
                    membership.version_id = version_by_instance[stable_name]
        db.flush()

        for route_index, _route_key in enumerate(route_specs, start=1):
            for instance_index, _stable_name in enumerate(INSTANCE_IDS, start=1):
                membership_identifier = membership_id(route_index, instance_index)
                desired = db.scalar(
                    select(DesiredRouteState).where(DesiredRouteState.membership_id == membership_identifier)
                )
                if desired is None:
                    db.add(
                        DesiredRouteState(
                            environment_id=environment.id,
                            membership_id=membership_identifier,
                            admin_state="ready",
                            weight=100,
                            controller_generation=environment.controller_generation,
                            source_action_id=None,
                        )
                    )

        if db.get(RoutingPolicy, IDS["routing_policy"]) is None:
            db.add(
                RoutingPolicy(
                    id=IDS["routing_policy"],
                    environment_id=environment.id,
                    route_id=None,
                    revision=1,
                    minimum_physical_reserve=50,
                    maximum_simultaneous_quarantine=1,
                    verification_settings={
                        "affected_effect_required": True,
                        "unaffected_preservation_required": True,
                        "minimum_real_samples": 12,
                        "deadline_seconds": 45,
                    },
                    reintegration_settings={
                        "stages": [5, 20, 50, 100],
                        "cooldown_seconds": 3,
                        "minimum_stage_samples": {"5": 2, "20": 4, "50": 6, "100": 8},
                        "maximum_flaps": 2,
                    },
                    action_allowlist=[
                        "ROUTE_MEMBERSHIP_DRAIN",
                        "INSTANCE_DRAIN",
                        "RETRY_SUPPRESSION",
                        "OVERLOAD_PROTECTION",
                        "VERSION_COHORT_DRAIN",
                    ],
                    active=True,
                )
            )
        else:
            policy = db.get(RoutingPolicy, IDS["routing_policy"])
            policy.verification_settings = {
                "profile": "LAB_DEMO_V1",
                "affected_effect_required": True,
                "unaffected_preservation_required": True,
                "minimum_real_samples": 12,
                "deadline_seconds": 45,
            }
            policy.reintegration_settings = {
                "profile": "LAB_DEMO_V1",
                "stages": [5, 20, 50, 100],
                "cooldown_seconds": 3,
                "minimum_stage_samples": {"5": 2, "20": 4, "50": 6, "100": 8},
                "maximum_flaps": 2,
            }

        for route_index, route_key in enumerate(route_specs, start=1):
            identifier = retry_policy_id(route_index)
            if db.get(RetryPolicy, identifier) is None:
                db.add(
                    RetryPolicy(
                        id=identifier,
                        route_id=ROUTE_IDS[route_key],
                        revision=1,
                        method_category="IDEMPOTENT_ONLY",
                        allowed_failures=["CONNECT_FAILURE", "HTTP_502", "HTTP_503", "HTTP_504"],
                        maximum_cross_instance_retries=1,
                        ambiguous_post_behavior="SUPPRESS_RETRY",
                        active=True,
                    )
                )

        db.flush()
        existing_audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.project_id == project.id,
                AuditEvent.event_type == "PROJECT_BOOTSTRAPPED",
            )
        )
        if existing_audit is None:
            append_audit(
                db,
                project=project,
                environment_id=environment.id,
                actor_user_id=user.id,
                event_type="PROJECT_BOOTSTRAPPED",
                subject_type="project",
                subject_id=str(project.id),
                before=None,
                after={"project_id": str(project.id), "mode": environment.mode},
                correlation_id="phase2-bootstrap",
            )
            add_outbox(
                db,
                project_id=project.id,
                environment_id=environment.id,
                event_type="registry.snapshot.created",
                aggregate_type="environment",
                aggregate_id=str(environment.id),
                aggregate_version=environment.version,
                correlation_id="phase2-bootstrap",
                payload={
                    "service_id": str(service.id),
                    "data": {
                        "route_count": 4,
                        "physical_instance_count": 3,
                        "logical_membership_count": 12,
                        "control_authority": "absent",
                    },
                },
            )
        db.commit()

    with session_factory() as db:
        publish_pending_outbox(db, get_redis(), project_id=IDS["project"])


if __name__ == "__main__":
    seed()
