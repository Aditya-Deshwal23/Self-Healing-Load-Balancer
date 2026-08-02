from __future__ import annotations

from typing import Any

from shlb_api.contracts import isoformat
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


def project_resource(row: Project, *, role: str | None = None) -> dict[str, Any]:
    data = {
        "id": str(row.id),
        "team_id": str(row.team_id),
        "name": row.name,
        "slug": row.slug,
        "status": row.status,
        "version": row.version,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }
    if role:
        data["role"] = role
    return data


def environment_resource(row: Environment) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "name": row.name,
        "kind": row.kind,
        "mode": row.mode,
        "timezone": row.timezone,
        "automation_frozen": row.automation_frozen,
        "controller_generation": row.controller_generation,
        "version": row.version,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }


def service_resource(row: Service) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "environment_id": str(row.environment_id),
        "name": row.name,
        "protocol": row.protocol,
        "status": row.status,
        "version": row.version,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }


def version_resource(row: DeploymentVersion) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "service_id": str(row.service_id),
        "version_label": row.version_label,
        "artifact_digest": row.artifact_digest,
        "deployed_at": isoformat(row.deployed_at) if row.deployed_at else None,
        "status": row.status,
        "version": row.version,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }


def backend_resource(row: BackendInstance) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "service_id": str(row.service_id),
        "version_id": str(row.version_id) if row.version_id else None,
        "stable_name": row.stable_name,
        "endpoint": {"address": "encrypted", "port": row.port},
        "capacity": row.capacity,
        "probe_profile": row.probe_profile,
        "status": row.status,
        "version": row.version,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }


def route_resource(row: RouteGroup) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "service_id": str(row.service_id),
        "route_key": row.route_key,
        "match_type": row.match_type,
        "match_value": row.match_value,
        "priority": row.priority,
        "criticality": row.criticality,
        "default_behavior": row.default_behavior,
        "version": row.version,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }


def membership_resource(row: RouteMembership) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "route_id": str(row.route_id),
        "instance_id": str(row.instance_id),
        "haproxy_backend": row.haproxy_backend,
        "haproxy_server": row.haproxy_server,
        "baseline_weight": row.baseline_weight,
        "baseline_maxconn": row.baseline_maxconn,
        "status": row.status,
        "desired_state": {
            "administrative_state": "READY" if row.status == "ACTIVE" else "DRAIN",
            "weight": row.baseline_weight,
        },
        "observed_state": {
            "status": "UNKNOWN",
            "reason": "HAProxy readback is not a Phase 2 API authority.",
        },
        "version": row.version,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }


def routing_policy_resource(row: RoutingPolicy) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "environment_id": str(row.environment_id),
        "route_id": str(row.route_id) if row.route_id else None,
        "revision": row.revision,
        "minimum_physical_reserve": row.minimum_physical_reserve,
        "maximum_simultaneous_quarantine": row.maximum_simultaneous_quarantine,
        "verification_settings": row.verification_settings,
        "reintegration_settings": row.reintegration_settings,
        "action_allowlist": row.action_allowlist,
        "active": row.active,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }


def retry_policy_resource(row: RetryPolicy) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "route_id": str(row.route_id),
        "revision": row.revision,
        "method_category": row.method_category,
        "allowed_failures": row.allowed_failures,
        "maximum_cross_instance_retries": row.maximum_cross_instance_retries,
        "ambiguous_post_behavior": row.ambiguous_post_behavior,
        "active": row.active,
        "created_at": isoformat(row.created_at),
        "updated_at": isoformat(row.updated_at),
    }
