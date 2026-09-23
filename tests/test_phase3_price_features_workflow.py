from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-price-features.yml")


def test_phase3_price_features_are_dispatch_only_and_outcome_blind():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase2-research-price-path" in text
    assert "phase2-outcome-labels" not in text
    assert "phase2-universe-outcome-dataset" not in text
    assert "materialize_phase3_price_features" in text
    assert "outcome_rows_consumed: false" in text


def test_phase3_price_features_publish_registry_and_future_row_guard():
    text = WORKFLOW.read_text()

    assert "phase3-feature-registry.json" in text
    assert "phase3-feature-registry-report.json" in text
    assert "feature_registry_sha256" in text
    assert "future_price_rows_used: false" in text
    assert "phase3_price_features_ready: true" in text
    assert "git push" not in text
    assert "contents: write" not in text
