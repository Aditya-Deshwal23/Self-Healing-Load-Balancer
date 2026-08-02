from __future__ import annotations

from dataclasses import dataclass


ROUTES = ("public", "auth", "catalog", "checkout")
INSTANCES = ("inst-a", "inst-b", "inst-c")
FAILURE_RATE = 0.5
HEALTHY_RATE = 0.1
TARGET_MINIMUM_SAMPLES = 6
CONTROL_MINIMUM_SAMPLES = 3


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

    target = checkout["inst-b"]
    peers_healthy = all(_healthy(checkout[instance], CONTROL_MINIMUM_SAMPLES) for instance in ("inst-a", "inst-c"))
    siblings_healthy = all(_healthy(instance_b_members[route], CONTROL_MINIMUM_SAMPLES) for route in ("public", "auth", "catalog"))
    target_probe = checkout_probes["inst-b"]
    comparison_probes = all(checkout_probes[instance].get("application_ok") is True for instance in ("inst-a", "inst-c")) and all(instance_b_probes[route].get("application_ok") is True for route in ("public", "auth", "catalog"))
    if _failing(target, TARGET_MINIMUM_SAMPLES) and peers_healthy and siblings_healthy and target_probe.get("reachable") is True and target_probe.get("application_ok") is False and comparison_probes:
        return RuleDecision(
            "ROUTE_INSTANCE_FAILURE", "checkout", "inst-b", 0.98, completeness,
            {
                "target": target,
                "same_route_peers": {key: checkout[key] for key in ("inst-a", "inst-c")},
                "same_instance_other_routes": {key: instance_b_members[key] for key in ("public", "auth", "catalog")},
                "endpoint_reachable": True,
            },
            [
                {"class": "INSTANCE_DOWN", "rejected": "three sibling routes on inst-b are healthy"},
                {"class": "SHARED_ROUTE_FAILURE", "rejected": "checkout peers inst-a and inst-c are healthy"},
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
    allowed = bool(total) and remaining_percent >= minimum_reserve_percent and all(value <= 5 for value in peer_queues.values())
    return {
        "allowed": allowed,
        "capacity_semantics": "unique physical instances",
        "total_physical_capacity": total,
        "remaining_physical_capacity": remaining,
        "remaining_percent": round(remaining_percent, 1),
        "minimum_reserve_percent": minimum_reserve_percent,
        "peer_queues": peer_queues,
        "queue_limit": 5,
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
    queues_safe = all(value <= 5 for queues in bounded_queues.values() for value in queues.values())
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
        "queue_limit": 5,
    }
