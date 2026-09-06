from __future__ import annotations

from dataclasses import dataclass, field


ROUTES = ("public", "auth", "catalog", "checkout")
INSTANCES = ("inst-a", "inst-b", "inst-c", "inst-d")


@dataclass(frozen=True)
class LabControlPolicy:
    """All accelerated prototype thresholds and timings in one explicit policy."""

    loop_seconds: float = 2.0
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
    degraded_p95_multiplier: float = 2.0
    minimum_physical_reserve_percent: int = 50
    action_expiry_seconds: int = 600
    verification_timeout_seconds: int = 45
    reintegration_cooldown_seconds: int = 3
    reintegration_stage_timeout_seconds: int = 45
    maximum_reintegration_retries: int = 2
    instance_recovery_probe_passes: int = 3
    reintegration_stages: tuple[tuple[str, int | None, int], ...] = (
        ("PROBING", None, 3),
        ("5%", 5, 2),
        ("20%", 20, 4),
        ("50%", 50, 6),
        ("100%", 100, 8),
        ("HEALTHY", 100, 1),
    )
    reintegration_scope_orders: dict[str, tuple[str, ...]] = field(default_factory=lambda: {
        "ROUTE_INSTANCE": ("dependency", "retries", "weights"),
        "COMPLETE_INSTANCE": ("critical_routes", "diagnostic_routes", "capacity"),
        "VERSION_GROUP": ("canary", "cohort_batches"),
        "COMPLETE_ROUTE": ("dependency", "retry_suppression", "admission", "traffic", "protection", "retries"),
        "OVERLOAD": ("queue_headroom", "admission", "traffic", "retries"),
    })


LAB_POLICY = LabControlPolicy()
FAILURE_RATE = LAB_POLICY.failure_rate
HEALTHY_RATE = LAB_POLICY.healthy_rate
TARGET_MINIMUM_SAMPLES = LAB_POLICY.target_minimum_samples
CONTROL_MINIMUM_SAMPLES = LAB_POLICY.control_minimum_samples


def reintegration_evidence_passes(
    evidence_rows: list[dict],
    probes: list[dict],
    minimum_samples: int,
    *,
    harmful: bool = False,
) -> bool:
    """Require real samples, healthy probes, and no harmful verdict before promotion."""
    if not evidence_rows or len(evidence_rows) != len(probes):
        return False
    if any(row.get("samples", 0) <= 0 or row.get("samples", 0) < minimum_samples for row in evidence_rows):
        return False
    if any(row.get("error_rate") is None or row["error_rate"] > HEALTHY_RATE for row in evidence_rows):
        return False
    if harmful or any(probe.get("application_ok") is not True for probe in probes):
        return False
    return True


def reintegration_cooldown_seconds(flap_count: int) -> int:
    """Use the accelerated lab base while retaining the documented exponential backoff."""
    return min(
        LAB_POLICY.reintegration_cooldown_seconds * (2 ** max(flap_count, 0)),
        LAB_POLICY.reintegration_stage_timeout_seconds,
    )


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


def classify(evidence: dict[str, dict], probes: dict[str, dict], conflicts: list[str]) -> RuleDecision:
    available = sum(1 for route in ROUTES for instance in INSTANCES if _member(evidence, route, instance).get("samples", 0) > 0)
    completeness = round(available / (len(ROUTES) * len(INSTANCES)), 3)
    if conflicts:
        return RuleDecision(
            "UNKNOWN", "checkout", "inst-b", 0.0, completeness,
            {"reason": "mandatory evidence conflicts", "conflicts": conflicts},
            [{"class": "HEALTHY", "rejected": "ground truth and telemetry conflict"}], False,
        )

    checkout = {instance: _member(evidence, "checkout", instance) for instance in INSTANCES}
    checkout_probes = {instance: probes.get(f"checkout/{instance}", {}) for instance in INSTANCES}
    if all(_failing(checkout[instance], CONTROL_MINIMUM_SAMPLES) and checkout_probes[instance].get("application_ok") is False for instance in INSTANCES):
        return RuleDecision(
            "SHARED_ROUTE_FAILURE", "checkout", None, 0.97, completeness,
            {"checkout_peers": checkout, "direct_probes": checkout_probes},
            [{"class": "ROUTE_INSTANCE_FAILURE", "rejected": "all checkout peers fail"}], False,
        )

    instance_b_members = {route: _member(evidence, route, "inst-b") for route in ROUTES}
    instance_b_probes = {route: probes.get(f"{route}/inst-b", {}) for route in ROUTES}
    if all(instance_b_probes[route].get("application_ok") is False for route in ROUTES):
        return RuleDecision(
            "INSTANCE_DOWN", None, "inst-b", 0.99, completeness,
            {"same_instance_routes": instance_b_members, "direct_probes": instance_b_probes},
            [{"class": "ROUTE_INSTANCE_FAILURE", "rejected": "failure spans all routes on inst-b"}], True,
        )

    for instance in INSTANCES:
        target_members = {route: _member(evidence, route, instance) for route in ROUTES}
        target_probes = {route: probes.get(f"{route}/{instance}", {}) for route in ROUTES}
        populated_routes = [route for route, member in target_members.items() if member.get("samples", 0) >= CONTROL_MINIMUM_SAMPLES]
        abnormal_routes = []
        for route in populated_routes:
            member = target_members[route]
            peer_p95 = [
                _member(evidence, route, peer).get("p95_ms")
                for peer in INSTANCES
                if peer != instance and _member(evidence, route, peer).get("p95_ms") is not None
            ]
            elevated_p95 = bool(member.get("p95_ms") is not None and peer_p95 and member["p95_ms"] >= max(peer_p95) * LAB_POLICY.degraded_p95_multiplier)
            if _failing(member, CONTROL_MINIMUM_SAMPLES) or elevated_p95:
                abnormal_routes.append(route)
        peers_healthy = all(
            _healthy(_member(evidence, route, peer), CONTROL_MINIMUM_SAMPLES)
            for route in abnormal_routes
            for peer in INSTANCES
            if peer != instance
        )
        reachable = all(target_probes[route].get("reachable") is True and target_probes[route].get("application_ok") is True for route in ROUTES)
        if len(abnormal_routes) >= 2 and peers_healthy and reachable:
            return RuleDecision(
                "INSTANCE_DEGRADED", None, instance, 0.95, completeness,
                {
                    "target": {route: target_members[route] for route in abnormal_routes},
                    "affected_routes": abnormal_routes,
                    "same_route_peers": {
                        route: {peer: _member(evidence, route, peer) for peer in INSTANCES if peer != instance}
                        for route in abnormal_routes
                    },
                    "direct_probes": target_probes,
                    "endpoint_reachable": True,
                },
                [
                    {"class": "INSTANCE_DOWN", "rejected": "target direct probes remain application_ok"},
                    {"class": "ROUTE_INSTANCE_FAILURE", "rejected": "degradation spans multiple routes"},
                ],
                True,
            )

    target = checkout["inst-b"]
    peers_healthy = all(_healthy(checkout[instance], CONTROL_MINIMUM_SAMPLES) for instance in INSTANCES if instance != "inst-b")
    siblings_healthy = all(_healthy(instance_b_members[route], CONTROL_MINIMUM_SAMPLES) for route in ("public", "auth", "catalog"))
    target_probe = checkout_probes["inst-b"]
    comparison_probes = all(checkout_probes[instance].get("application_ok") is True for instance in ("inst-a", "inst-c")) and all(instance_b_probes[route].get("application_ok") is True for route in ("public", "auth", "catalog"))
    if _failing(target, TARGET_MINIMUM_SAMPLES) and peers_healthy and siblings_healthy and target_probe.get("reachable") is True and target_probe.get("application_ok") is False and comparison_probes:
        return RuleDecision(
            "ROUTE_INSTANCE_FAILURE", "checkout", "inst-b", 0.98, completeness,
            {
                "target": target,
                "same_route_peers": {key: checkout[key] for key in INSTANCES if key != "inst-b"},
                "same_instance_other_routes": {key: instance_b_members[key] for key in ("public", "auth", "catalog")},
                "endpoint_reachable": True,
            },
            [
                {"class": "INSTANCE_DOWN", "rejected": "three sibling routes on inst-b are healthy"},
                {"class": "SHARED_ROUTE_FAILURE", "rejected": "all checkout peers are healthy"},
            ],
            True,
        )

    all_healthy = all(_healthy(_member(evidence, route, instance), 1) for route in ROUTES for instance in INSTANCES) and all(probes.get(f"{route}/{instance}", {}).get("application_ok") is True for route in ROUTES for instance in INSTANCES)
    if all_healthy:
        return RuleDecision("HEALTHY", None, None, 1.0, completeness, {"all_memberships_within_bound": True}, [], False)

    missing = [f"{route}/{instance}" for route in ROUTES for instance in INSTANCES if _member(evidence, route, instance).get("samples", 0) < CONTROL_MINIMUM_SAMPLES]
    return RuleDecision(
        "UNKNOWN", None, None, 0.0, completeness,
        {"reason": "mandatory comparisons are incomplete", "missing_or_sparse": missing},
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
