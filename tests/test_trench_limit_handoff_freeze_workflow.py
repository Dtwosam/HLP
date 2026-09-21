from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-trench-limit-handoff-freeze.yml"
)


def test_trench_handoff_freeze_is_dispatch_only_and_evidence_bound():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "evidence_run_id:" in text
    assert "expected_evidence_artifact_digest:" in text
    assert "expected_evidence_report_sha256:" in text
    assert "trench evidence artifact digest drift" in text
    assert "trench evidence report SHA drift" in text
    assert "trench candidate manifest SHA drift" in text


def test_trench_handoff_freeze_is_strict_and_nonfinal():
    text = WORKFLOW.read_text()

    assert "freeze_trench_limit_market_handoffs" in text
    assert "all_limit_reach_tokens_resolved" in text
    assert "handoff_rule_frozen" in text
    assert "trench-limit-same-transaction-after-v1" in text
    assert "source_coverage_complete: false" in text
    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text
