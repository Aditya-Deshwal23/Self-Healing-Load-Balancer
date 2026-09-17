from __future__ import annotations

from dataclasses import dataclass


ROUTES = ("public", "auth", "catalog", "checkout")
INSTANCES = ("inst-a", "inst-b", "inst-c")


@dataclass(frozen=True)
class LabControlPolicy:
    """All accelerated prototype thresholds and timings in one explicit policy."""

    loop_seconds: float = 0.5
    observation_window_seconds: int = 12
    worker_lease_seconds: int = 10
    heartbeat_stale_seconds: int = 10
    failure_rate: float = 0.5
    healthy_rate: float = 0.1
    harmful_error_rate: float = 0.25
    target_minimum_samples: int = 6
    control_minimum_samples: int = 3
    route_verification_minimum_samples: int = 12
    instance_route_minimum_samples: int = 6
    peer_queue_limit: int = 5
    harmful_queue_limit: int = 10
    minimum_physical_reserve_percent: int = 50
    action_expiry_seconds: int = 600
    verification_timeout_seconds: int = 45
    reintegration_cooldown_seconds: int = 3
    reintegration_stage_timeout_seconds: int = 45
    maximum_reintegration_retries: int = 2
    instance_recovery_probe_passes: int = 3
    hybrid_shadow_enabled: bool = True          # HYBRID_SHADOW gate: advisory fast-path signal; never actuates
    reintegration_stages: tuple[tuple[str, int | None, int], ...] = (
        ("PROBING", None, 3),
        ("5%", 5, 2),
        ("20%", 20, 4),
        ("50%", 50, 6),
        ("100%", 100, 8),
        ("HEALTHY", 100, 1),
    )


LAB_POLICY = LabControlPolicy()
FAILURE_RATE = LAB_POLICY.failure_rate
HEALTHY_RATE = LAB_POLICY.healthy_rate
TARGET_MINIMUM_SAMPLES = LAB_POLICY.target_minimum_samples
CONTROL_MINIMUM_SAMPLES = LAB_POLICY.control_minimum_samples


@dataclass(frozen=True)
class RuleDecision:
    final_class: str
    route: str | None
    instance: str | None
    confidence: float
    completeness: float
    support: dict
    competing: list[dict]
    actionable: bool


def _member(evidence: dict[str, dict], route: str, instance: str) -> dict:
    return evidence.get(f"{route}/{instance}", {"samples": 0, "error_rate": None, "p95_ms": None})


def _healthy(member: dict, minimum_samples: int) -> bool:
    return member.get("samples", 0) >= minimum_samples and member.get("error_rate") is not None and member["error_rate"] <= HEALTHY_RATE


def _failing(member: dict, minimum_samples: int) -> bool:
    return member.get("samples", 0) >= minimum_samples and member.get("error_rate") is not None and member["error_rate"] >= FAILURE_RATE


def classify(
    evidence: dict[str, dict],
    probes: dict[str, dict],
    conflicts: list[str],
    statistical_support: dict[str, dict] | None = None,
) -> RuleDecision:
    """Evaluate every (route, instance) cell in the registered topology.

    ``statistical_support`` (the fast-path EWMA recommendations) is
    advisory-only evidence: it is attached to whichever decision the
    deterministic rules already reached so it is visible in the Decision
    Trace and the evidence certificate. It never changes ``final_class`` or
    ``actionable`` on its own. Actuation authority stays with the rule
    branches below, per ADR "Rules-first hard gates ... ML may enter
    HYBRID_ACTIVE only after ...".
    """
    statistical_support = statistical_support or {}
    available = sum(1 for route in ROUTES for instance in INSTANCES if _member(evidence, route, instance).get("samples", 0) > 0)
    completeness = round(available / (len(ROUTES) * len(INSTANCES)), 3)

    if conflicts:
        return RuleDecision(
            "UNKNOWN", None, None, 0.0, completeness,
            {"reason": "mandatory evidence conflicts", "conflicts": conflicts, "shadow_statistical_signal": statistical_support},
            [{"class": "HEALTHY", "rejected": "ground truth and telemetry conflict"}], False,
        )

    # 1. SHARED_ROUTE_FAILURE: every physical instance serving this route fails.
    for route in ROUTES:
        route_members = {instance: _member(evidence, route, instance) for instance in INSTANCES}
        route_probes = {instance: probes.get(f"{route}/{instance}", {}) for instance in INSTANCES}
        if all(_failing(route_members[instance], CONTROL_MINIMUM_SAMPLES) and route_probes[instance].get("application_ok") is False for instance in INSTANCES):
            return RuleDecision(
                "SHARED_ROUTE_FAILURE", route, None, 0.97, completeness,
                {"route_peers": route_members, "direct_probes": route_probes, "shadow_statistical_signal": statistical_support},
                [{"class": "ROUTE_INSTANCE_FAILURE", "rejected": f"all {route} peers fail"}], False,
            )

    # 2. INSTANCE_DOWN: every route served by this physical instance fails.
    for instance in INSTANCES:
        instance_members = {route: _member(evidence, route, instance) for route in ROUTES}
        instance_probes = {route: probes.get(f"{route}/{instance}", {}) for route in ROUTES}
        if all(instance_probes[route].get("application_ok") is False for route in ROUTES):
            return RuleDecision(
                "INSTANCE_DOWN", None, instance, 0.99, completeness,
                {"same_instance_routes": instance_members, "direct_probes": instance_probes, "shadow_statistical_signal": statistical_support},
                [{"class": "ROUTE_INSTANCE_FAILURE", "rejected": f"failure spans all routes on {instance}"}], True,
            )

    # 3. ROUTE_INSTANCE_FAILURE: exactly one cell fails while its route peers
    #    and instance siblings stay healthy and reachable.
    for route in ROUTES:
        for instance in INSTANCES:
            target = _member(evidence, route, instance)
            peer_instances = [other for other in INSTANCES if other != instance]
            sibling_routes = [other for other in ROUTES if other != route]
            peers_healthy = all(_healthy(_member(evidence, route, peer), CONTROL_MINIMUM_SAMPLES) for peer in peer_instances)
            siblings_healthy = all(_healthy(_member(evidence, sibling, instance), CONTROL_MINIMUM_SAMPLES) for sibling in sibling_routes)
            target_probe = probes.get(f"{route}/{instance}", {})
            comparison_probes = (
                all(probes.get(f"{route}/{peer}", {}).get("application_ok") is True for peer in peer_instances)
                and all(probes.get(f"{sibling}/{instance}", {}).get("application_ok") is True for sibling in sibling_routes)
            )
            if (
                _failing(target, TARGET_MINIMUM_SAMPLES)
                and peers_healthy and siblings_healthy
                and target_probe.get("reachable") is True
                and target_probe.get("application_ok") is False
                and comparison_probes
            ):
                return RuleDecision(
                    "ROUTE_INSTANCE_FAILURE", route, instance, 0.98, completeness,
                    {
                        "target": target,
                        "same_route_peers": {peer: _member(evidence, route, peer) for peer in peer_instances},
                        "same_instance_other_routes": {sibling: _member(evidence, sibling, instance) for sibling in sibling_routes},
                        "endpoint_reachable": True,
                        "shadow_statistical_signal": statistical_support,
                    },
                    [
                        {"class": "INSTANCE_DOWN", "rejected": f"sibling routes on {instance} are healthy"},
                        {"class": "SHARED_ROUTE_FAILURE", "rejected": f"{route} peers on other instances are healthy"},
                    ],
                    True,
                )

    # 4. HEALTHY: every cell in the topology is within bound and reachable.
    all_healthy = all(_healthy(_member(evidence, route, instance), 1) for route in ROUTES for instance in INSTANCES) and all(
        probes.get(f"{route}/{instance}", {}).get("application_ok") is True for route in ROUTES for instance in INSTANCES
    )
    if all_healthy:
        return RuleDecision(
            "HEALTHY", None, None, 1.0, completeness,
            {"all_memberships_within_bound": True, "shadow_statistical_signal": statistical_support},
            [], False,
        )

    # 5. UNKNOWN: evidence is incomplete or does not support any single scoped hypothesis.
    missing = [f"{route}/{instance}" for route in ROUTES for instance in INSTANCES if _member(evidence, route, instance).get("samples", 0) < CONTROL_MINIMUM_SAMPLES]
    return RuleDecision(
        "UNKNOWN", None, None, 0.0, completeness,
        {"reason": "mandatory comparisons are incomplete", "missing_or_sparse": missing, "shadow_statistical_signal": statistical_support},
        [
            {"class": "ROUTE_INSTANCE_FAILURE", "rejected": "mandatory peer or sibling comparison missing"},
            {"class": "INSTANCE_DOWN", "rejected": "scope is not supported by complete evidence"},
        ], False,
    )


def route_instance_capacity(*, capacities: dict[str, int], target_instance: str, queues: dict[str, int], minimum_reserve_percent: int) -> dict:
    total = sum(capacities.values())
    remaining = sum(value for instance, value in capacities.items() if instance != target_instance)
    remaining_percent = (remaining / total * 100) if total else 0
    peer_queues = {instance: queues.get(instance, 0) for instance in capacities if instance != target_instance}
    allowed = bool(total) and remaining_percent >= minimum_reserve_percent and all(value <= LAB_POLICY.peer_queue_limit for value in peer_queues.values())
    return {
        "allowed": allowed,
        "capacity_semantics": "unique physical instances",
        "total_physical_capacity": total,
        "remaining_physical_capacity": remaining,
        "remaining_percent": round(remaining_percent, 1),
        "minimum_reserve_percent": minimum_reserve_percent,
        "peer_queues": peer_queues,
        "queue_limit": LAB_POLICY.peer_queue_limit,
    }


def instance_capacity(*, capacities: dict[str, int], target_instance: str, route_peer_queues: dict[str, dict[str, int]], minimum_reserve_percent: int) -> dict:
    """Evaluate an instance drain without multiplying physical capacity by route memberships."""
    total = sum(capacities.values())
    remaining = sum(value for instance, value in capacities.items() if instance != target_instance)
    remaining_percent = (remaining / total * 100) if total else 0
    bounded_queues = {
        route: {instance: value for instance, value in queues.items() if instance != target_instance}
        for route, queues in route_peer_queues.items()
    }
    all_routes_have_two_peers = all(len(queues) == len(capacities) - 1 for queues in bounded_queues.values())
    queues_safe = all(value <= LAB_POLICY.peer_queue_limit for queues in bounded_queues.values() for value in queues.values())
    allowed = bool(total) and remaining_percent >= minimum_reserve_percent and all_routes_have_two_peers and queues_safe
    return {
        "allowed": allowed,
        "capacity_semantics": "unique physical instances counted once",
        "total_physical_capacity": total,
        "remaining_physical_capacity": remaining,
        "remaining_percent": round(remaining_percent, 1),
        "minimum_reserve_percent": minimum_reserve_percent,
        "route_peer_queues": bounded_queues,
        "all_routes_have_two_peers": all_routes_have_two_peers,
        "queue_limit": LAB_POLICY.peer_queue_limit,
    }
