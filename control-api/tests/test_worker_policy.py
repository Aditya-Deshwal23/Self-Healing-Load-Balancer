from __future__ import annotations

from shlb_api.worker_policy import (
    INSTANCES,
    LAB_POLICY,
    ROUTES,
    classify,
    instance_capacity,
    reintegration_cooldown_seconds,
    reintegration_evidence_passes,
    route_instance_capacity,
)


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


def test_accelerated_lab_timings_are_centralized_and_bounded() -> None:
    assert LAB_POLICY.observation_window_seconds == 12
    assert LAB_POLICY.reintegration_cooldown_seconds == 3
    assert [stage[0] for stage in LAB_POLICY.reintegration_stages] == [
        "PROBING",
        "5%",
        "20%",
        "50%",
        "100%",
        "HEALTHY",
    ]
    assert LAB_POLICY.maximum_reintegration_retries == 2
    assert LAB_POLICY.peer_queue_limit < LAB_POLICY.harmful_queue_limit


def test_reintegration_matrix_rejects_zero_sparse_harmful_and_flapping_verdicts() -> None:
    phase_one_classes = (
        "ROUTE_INSTANCE_FAILURE",
        "INSTANCE_DOWN",
        "INSTANCE_DEGRADED",
        "SHARED_ROUTE_FAILURE",
        "VERSION_SPECIFIC_FAILURE",
        "TRAFFIC_OVERLOAD",
    )
    healthy = [{"samples": 8, "error_rate": 0.0}]
    probes_ok = [{"application_ok": True}]
    for _fault_class in phase_one_classes:
        assert reintegration_evidence_passes(healthy, probes_ok, 3)
        assert not reintegration_evidence_passes([{"samples": 0, "error_rate": 0.0}], probes_ok, 3)
        assert not reintegration_evidence_passes([{"samples": 2, "error_rate": 0.0}], probes_ok, 3)
        assert not reintegration_evidence_passes([{"samples": 8, "error_rate": 0.4}], probes_ok, 3)
        assert not reintegration_evidence_passes(healthy, probes_ok, 3, harmful=True)
        assert not reintegration_evidence_passes(healthy, [{"application_ok": False}], 3)


def test_zero_sample_windows_never_pass_for_any_reintegration_scope() -> None:
    scopes = ("ROUTE_INSTANCE", "COMPLETE_INSTANCE", "VERSION_GROUP", "COMPLETE_ROUTE", "OVERLOAD")
    for _scope in scopes:
        assert not reintegration_evidence_passes(
            [{"samples": 0, "error_rate": None}],
            [{"application_ok": True}],
            1,
        )


def test_reintegration_flapping_uses_accelerated_exponential_cooldown() -> None:
    assert reintegration_cooldown_seconds(0) == 3
    assert reintegration_cooldown_seconds(1) == 6
    assert reintegration_cooldown_seconds(2) == 12
    assert reintegration_cooldown_seconds(10) == LAB_POLICY.reintegration_stage_timeout_seconds


def test_reintegration_scope_restore_orders_are_distinct() -> None:
    assert LAB_POLICY.reintegration_scope_orders["ROUTE_INSTANCE"] == ("dependency", "retries", "weights")
    assert LAB_POLICY.reintegration_scope_orders["COMPLETE_INSTANCE"] == (
        "critical_routes",
        "diagnostic_routes",
        "capacity",
    )
    assert LAB_POLICY.reintegration_scope_orders["VERSION_GROUP"] == ("canary", "cohort_batches")
    assert LAB_POLICY.reintegration_scope_orders["COMPLETE_ROUTE"][-1] == "retries"
    assert LAB_POLICY.reintegration_scope_orders["OVERLOAD"][-1] == "retries"
    assert LAB_POLICY.reintegration_scope_orders["COMPLETE_ROUTE"] != LAB_POLICY.reintegration_scope_orders["ROUTE_INSTANCE"]


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


def test_instance_degraded_requires_two_routes_reachability_and_healthy_peers() -> None:
    degraded = evidence()
    for route in ("public", "auth"):
        degraded[f"{route}/inst-b"] = {"samples": 12, "errors": 6, "error_rate": 0.5, "p95_ms": 20.0}
    decision = classify(degraded, probes(), [])
    assert decision.final_class == "INSTANCE_DEGRADED"
    assert decision.actionable is True
    assert decision.instance == "inst-b"
    assert set(decision.support["affected_routes"]) == {"public", "auth"}

    one_route = evidence()
    one_route["public/inst-b"] = {"samples": 12, "errors": 6, "error_rate": 0.5, "p95_ms": 20.0}
    assert classify(one_route, probes(), []).final_class == "UNKNOWN"

    down = probes(failing={("public", "inst-b"), ("auth", "inst-b")})
    assert classify(degraded, down, []).final_class == "INSTANCE_DOWN"


def test_instance_degraded_accepts_elevated_populated_p95() -> None:
    elevated = evidence()
    for route in ("public", "auth"):
        elevated[f"{route}/inst-b"] = {"samples": 12, "errors": 0, "error_rate": 0.0, "p95_ms": 10.0}
        for peer in ("inst-a", "inst-c"):
            elevated[f"{route}/{peer}"]["p95_ms"] = 2.0
    decision = classify(elevated, probes(), [])
    assert decision.final_class == "INSTANCE_DEGRADED"


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
