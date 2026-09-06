from shlb_api.seed import IDS, INSTANCE_IDS, V1_INSTANCES, V2_INSTANCES


def test_seeded_version_cohorts_match_controlled_topology() -> None:
    assert set(INSTANCE_IDS) == {"inst-a", "inst-b", "inst-c", "inst-d"}
    assert IDS["version"] != IDS["version_v2"]
    assert V1_INSTANCES == ("inst-a", "inst-b")
    assert V2_INSTANCES == ("inst-c", "inst-d")
