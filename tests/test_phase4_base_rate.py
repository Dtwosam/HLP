import pytest

from hlp.data.phase4_base_rate import (
    PHASE4_BASE_RATE_HANDOFF_VERSION,
    PHASE4_BASE_RATE_REPORT_VERSION,
    build_phase4_base_rate_handoff,
    build_phase4_base_rate_report,
)


SHA = "ab" * 32
TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20
TOKEN_C = "0x" + "33" * 20


def handoff():
    return {
        "version": "phase4-discovery-entry-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_rows_sha256": SHA,
        "discovery_subjects": 3,
        "comeback_5x_tokens": 2,
        "comeback_5x_base_rate": "0.6666666666666666666666666667",
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_only": True,
        "phase4_discovery_entry_ready": True,
        "phase4_discovery_checkpoint_claimed": False,
    }


def row(token, multiple, censored=True):
    value = str(multiple)
    number = float(multiple)
    return {
        "version": "phase4-discovery-entry-v1",
        "token": token,
        "target_comeback_5x": number >= 5,
        "target_max_post_dump_multiple": value,
        "outcome": {
            "outcome_eligible": True,
            "dump_status": "confirmed",
            "max_post_dump_multiple": value,
            "right_censored_at_snapshot": censored,
            "reached_2x": number >= 2,
            "reached_3x": number >= 3,
            "reached_5x": number >= 5,
            "reached_10x": number >= 10,
        },
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_only": True,
    }


def test_base_rate_reports_population_before_feature_tests():
    report = build_phase4_base_rate_report(
        [
            row(TOKEN_A, "2"),
            row(TOKEN_B, "6"),
            row(TOKEN_C, "24"),
        ],
        discovery_entry_handoff=handoff(),
    )

    assert report["version"] == PHASE4_BASE_RATE_REPORT_VERSION
    assert report["discovery_subjects"] == 3
    assert report["comeback_5x_tokens"] == 2
    assert report["non_comeback_5x_tokens"] == 1
    assert report["milestones"]["5"]["reached_tokens"] == 2
    assert report["milestones"]["10"]["reached_tokens"] == 1
    distribution = report["max_post_dump_multiple_distribution"]
    assert distribution["minimum"] == "2"
    assert distribution["median"] == "6"
    assert distribution["mean"] == "10.66666666666666666666666667"
    assert distribution["maximum"] == "24"
    assert distribution["ge_20x_tokens"] == 1
    assert report["feature_relationships_tested"] is False
    assert report["signal_promoted"] is False
    assert report["phase4_discovery_checkpoint_claimed"] is False


def test_base_rate_rejects_milestone_drift():
    bad = row(TOKEN_A, "6")
    bad["outcome"]["reached_5x"] = False

    local = handoff()
    local["discovery_subjects"] = 1
    local["comeback_5x_tokens"] = 1
    local["comeback_5x_base_rate"] = "1"
    with pytest.raises(ValueError, match="milestone/magnitude disagree"):
        build_phase4_base_rate_report(
            [bad],
            discovery_entry_handoff=local,
        )


def test_base_rate_handoff_never_promotes_signal():
    report = {
        "version": PHASE4_BASE_RATE_REPORT_VERSION,
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_rows_sha256": SHA,
        "discovery_subjects": 10,
        "comeback_5x_tokens": 2,
        "comeback_5x_base_rate": "0.2",
        "winner_failure_frequencies_reported": True,
        "continuous_outcome_distribution_reported": True,
        "feature_relationships_tested": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_base_rate_report_ready": True,
    }
    result = build_phase4_base_rate_handoff(
        report,
        report_sha256=SHA,
        discovery_entry_handoff_sha256=SHA,
    )
    assert result["version"] == PHASE4_BASE_RATE_HANDOFF_VERSION
    assert result["feature_relationships_tested"] is False
    assert result["signal_promoted"] is False
    assert result["phase4_discovery_checkpoint_claimed"] is False
