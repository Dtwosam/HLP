from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-eligibility-handoff.yml"
)


def test_direct_eligibility_handoff_is_dispatch_only_and_exactly_bound():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "expected_selector_artifact_digest:" in text
    assert "expected_selector_descriptor_sha256:" in text
    for source in (
        "direct_uniswap_v3",
        "direct_sushiswap_v3",
        "direct_uniswap_v4",
    ):
        assert f"phase2-direct-source-coverage-{source}" in text
        assert (
            f"phase2-direct-source-coverage-price-{source}-*"
            in text
        )
    assert "coverage report SHA drift" in text
    assert "point shard SHA drift" in text
    assert "aggregate point SHA drift" in text


def test_direct_eligibility_applies_selector_once_after_full_coverage():
    text = WORKFLOW.read_text()

    assert "heapq.merge" in text
    assert "iter_frozen_direct_canonical_series" in text
    assert "expected_tokens=expected_tokens" in text
    assert "coverage already applied selector" in text
    assert "build_direct_eligibility_handoff" in text
    assert "direct-canonical-market-cap-points.jsonl" in text
    assert "direct-canonical-token-summary.jsonl" in text
    assert "cross_pool_volume_double_counting_allowed" not in text


def test_direct_eligibility_emits_three_universe_source_files_nonmutating():
    text = WORKFLOW.read_text()

    assert "phase2-source-eligibility-{source}.jsonl" in text
    assert "direct-eligibility-handoff.json" in text
    assert "phase2-direct-eligibility-handoff" in text
    assert "phase2_universe_source_ready: true" in text
    assert "phase2_universe_frozen: false" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
