from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-research-materialize-pons.yml"
)


def test_pons_research_materializer_is_dispatch_only_and_source_limited():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "- pons_v1" in text
    assert "- pons_v2" in text
    assert "resolve_accepted_pons_replay_inputs" in text
    assert "resolve_v1_v3_canonical_shard_bindings" in text
    assert "resolve_v2_v4_canonical_shard_bindings" in text
    assert "materialize_bound_shards" in text
    assert "materialize_pons_v1_research" in text
    assert "materialize_pons_v2_research" in text


def test_pons_research_materializer_binds_accepted_lifecycle_and_replay_equivalence():
    text = WORKFLOW.read_text()

    assert "accepted lifecycle summary SHA drift" in text
    assert "accepted lifecycle manifest SHA drift" in text
    assert "accepted lifecycle binding drift" in text
    assert "canonical market shard binding drift" in text
    assert "eligible_token_coverage_complete" in text
    assert "accepted_lifecycle_replay_equivalent" in text
    assert "research_component_ready: true" in text
    assert "dump_threshold_frozen: false" in text
    assert "outcome_labels_computed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
