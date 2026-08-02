from __future__ import annotations

from shlb_api.worker_policy import INSTANCES, ROUTES, classify, instance_capacity, route_instance_capacity


def evidence(*, failing: set[tuple[str, str]] | None = None, samples: int = 12) -> dict[str, dict]:
    failing = failing or set()
    return {
        f"{route}/{instance}": {
            "samples": samples,
            "errors": samples if (route, instance) in failing else 0,
            "error_rate": 1.0 if (route, instance) in failing else 0.0,
            "p95_ms": 2.0,
        }
        for route in ROUTES
        for instance in INSTANCES
    }


def probes(*, failing: set[tuple[str, str]] | None = None) -> dict[str, dict]:
    failing = failing or set()
    return {
        f"{route}/{instance}": {
            "reachable": True,
            "application_ok": (route, instance) not in failing,
            "status": 503 if (route, instance) in failing else 200,
        }
        for route in ROUTES
        for instance in INSTANCES
    }


def test_healthy_requires_every_membership_and_probe() -> None:
    decision = classify(evidence(), probes(), [])
    assert decision.final_class == "HEALTHY"
    assert decision.actionable is False


def test_route_instance_requires_healthy_route_peers_and_instance_siblings() -> None:
    failed = {("checkout", "inst-b")}
    decision = classify(evidence(failing=failed), probes(failing=failed), [])
    assert decision.final_class == "ROUTE_INSTANCE_FAILURE"
    assert decision.actionable is True
    assert decision.route == "checkout"
    assert decision.instance == "inst-b"
    assert {item["class"] for item in decision.competing} == {"INSTANCE_DOWN", "SHARED_ROUTE_FAILURE"}


def test_shared_route_is_non_destructive() -> None:
    failed = {("checkout", instance) for instance in INSTANCES}
    decision = classify(evidence(failing=failed), probes(failing=failed), [])
    assert decision.final_class == "SHARED_ROUTE_FAILURE"
    assert decision.actionable is False


def test_instance_down_is_actionable_at_physical_scope() -> None:
    failed = {(route, "inst-b") for route in ROUTES}
    decision = classify(evidence(failing=failed), probes(failing=failed), [])
    assert decision.final_class == "INSTANCE_DOWN"
    assert decision.actionable is True
    assert decision.route is None
    assert decision.instance == "inst-b"


def test_conflict_and_missing_mandatory_comparison_are_unknown() -> None:
    conflict = classify(evidence(), probes(), ["conflicting_source"])
    assert conflict.final_class == "UNKNOWN"
    assert conflict.actionable is False

    sparse = evidence(samples=0)
    sparse["checkout/inst-b"] = {"samples": 12, "errors": 12, "error_rate": 1.0, "p95_ms": 2.0}
    incomplete = classify(sparse, probes(failing={("checkout", "inst-b")}), [])
    assert incomplete.final_class == "UNKNOWN"
    assert incomplete.actionable is False


def test_route_capacity_counts_each_physical_backend_once() -> None:
    result = route_instance_capacity(
        capacities={"inst-a": 100, "inst-b": 100, "inst-c": 100},
        target_instance="inst-b",
        queues={"inst-a": 0, "inst-b": 0, "inst-c": 1},
        minimum_reserve_percent=50,
    )
    assert result["total_physical_capacity"] == 300
    assert result["remaining_physical_capacity"] == 200
    assert result["remaining_percent"] == 66.7
    assert result["allowed"] is True


def test_instance_capacity_does_not_multiply_capacity_by_four_routes() -> None:
    queues = {route: {"inst-a": 0, "inst-b": 0, "inst-c": 0} for route in ROUTES}
    result = instance_capacity(
        capacities={"inst-a": 100, "inst-b": 100, "inst-c": 100},
        target_instance="inst-b",
        route_peer_queues=queues,
        minimum_reserve_percent=50,
    )
    assert result["capacity_semantics"] == "unique physical instances counted once"
    assert result["total_physical_capacity"] == 300
    assert result["remaining_physical_capacity"] == 200
    assert result["allowed"] is True


def test_instance_capacity_rejects_missing_route_peer_or_queue_pressure() -> None:
    queues = {route: {"inst-a": 0, "inst-b": 0, "inst-c": 0} for route in ROUTES}
    queues["checkout"].pop("inst-c")
    assert instance_capacity(capacities={"inst-a": 100, "inst-b": 100, "inst-c": 100}, target_instance="inst-b", route_peer_queues=queues, minimum_reserve_percent=50)["allowed"] is False
    queues["checkout"]["inst-c"] = 6
    assert instance_capacity(capacities={"inst-a": 100, "inst-b": 100, "inst-c": 100}, target_instance="inst-b", route_peer_queues=queues, minimum_reserve_percent=50)["allowed"] is False
