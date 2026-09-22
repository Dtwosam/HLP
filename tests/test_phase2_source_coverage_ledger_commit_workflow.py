from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-source-coverage-ledger-commit.yml"
)


def test_ledger_commit_is_dispatch_only_explicit_and_serialized():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "apply_proposed_ledger:" in text
    assert "default: false" in text
    assert "canonical Phase-2 ledger write requires explicit approval" in text
    assert "cancel-in-progress: false" in text
    assert "contents: write" in text
    assert "actions: read" in text


def test_ledger_commit_is_exact_artifact_and_sha_bound():
    text = WORKFLOW.read_text()

    assert "promotion_run_id:" in text
    assert "expected_artifact_digest:" in text
    assert "expected_handoff_sha256:" in text
    assert "expected_proposed_ledger_sha256:" in text
    assert "promotion artifact digest drift" in text
    assert "promotion handoff SHA drift" in text
    assert "proposed ledger SHA drift" in text
    assert "proposed ledger/handoff SHA linkage drift" in text


def test_ledger_commit_rejects_stale_or_multi_source_proposals():
    text = WORKFLOW.read_text()

    assert "base_ledger_sha256" in text
    assert "current canonical ledger SHA drift; promotion is stale" in text
    assert "proposed ledger regresses complete sources" in text
    assert "proposed ledger must complete exactly the expected" in text
    assert "validate_phase2_coverage_ledger" in text


def test_ledger_commit_uses_atomic_contents_api_update():
    text = WORKFLOW.read_text()

    assert ".github/phase2-source-coverage.json" in text
    assert '"sha": metadata["sha"]' in text
    assert '"branch": ref' in text
    assert '"PUT"' in text
    assert "canonical_ledger_commit_sha" in text
    assert '"canonical_ledger_mutated": True' in text
