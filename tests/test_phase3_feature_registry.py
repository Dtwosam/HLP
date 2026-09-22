import copy

import pytest

from hlp.data.phase3_feature_registry import (
    PHASE3_FEATURE_REGISTRY_VERSION,
    build_phase3_feature_registry,
    validate_phase3_feature_registry,
)


def test_phase3_feature_registry_is_versioned_causal_and_outcome_blind():
    registry = build_phase3_feature_registry()
    report = validate_phase3_feature_registry(registry)

    assert report["version"] == PHASE3_FEATURE_REGISTRY_VERSION
    assert report["features"] == 80
    assert report["families"] == [
        "chain_regime",
        "early_recipient_activity",
        "holder_state",
        "lifecycle_age",
        "participant_retention",
        "price_drawdown",
        "supply_redistribution",
        "trade_flow",
        "trade_size_flow",
        "venue_mechanics",
    ]
    assert report["future_state_allowed"] is False
    assert report["outcome_dependency_allowed"] is False
    assert len(report["registry_sha256"]) == 64

    for row in registry:
        assert row["formula"]
        assert row["snapshot_kind"] == "first_major_dump_confirmation"
        assert row["cutoff_inclusive"] is True
        assert row["future_state_allowed"] is False
        assert row["outcome_dependency_allowed"] is False
        assert row["missingness_policy"] in {
            "error_if_missing",
            "null_with_flag",
            "zero_if_no_observations",
        }


def test_phase3_feature_registry_sha_changes_when_formula_changes():
    registry = build_phase3_feature_registry()
    original = validate_phase3_feature_registry(registry)

    changed = copy.deepcopy(registry)
    changed[0]["formula"] += " changed"
    revised = validate_phase3_feature_registry(changed)

    assert revised["registry_sha256"] != original["registry_sha256"]


def test_phase3_feature_registry_rejects_future_or_outcome_dependency():
    registry = build_phase3_feature_registry()
    registry[0]["future_state_allowed"] = True

    with pytest.raises(ValueError, match="allows future state"):
        validate_phase3_feature_registry(registry)

    registry = build_phase3_feature_registry()
    registry[0]["outcome_dependency_allowed"] = True
    with pytest.raises(ValueError, match="depends on outcomes"):
        validate_phase3_feature_registry(registry)
