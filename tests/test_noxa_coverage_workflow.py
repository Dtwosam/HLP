from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-noxa-source-coverage.yml"
)


def test_noxa_coverage_is_dispatch_only_and_reuses_shared_surfaces():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "registry_run_id:" in text
    assert "v3_initialize_run_id:" in text
    assert "v3_swap_run_id:" in text
    assert "supply_delta_run_id:" in text
    assert "quote_run_id:" in text
    assert "phase2-direct-v3-initialize-merged" in text
    assert "phase2-direct-v3-swap-${{ matrix.shard }}" in text
    assert "phase2-direct-supply-delta-manifest" in text
    assert "pattern: phase2-direct-supply-delta-*" in text


def test_noxa_coverage_replays_supply_and_requires_priceable_quotes():
    text = WORKFLOW.read_text()

    assert "phase2-noxa-initialized-registry" in text
    assert "phase2-noxa-market-window" in text
    assert "--supply-deltas inputs/setup/noxa-supply-deltas.jsonl" in text
    assert "end-of-launch-block seed plus causal mint/burn" in text
    assert "NOXA registry includes unsupported V3 factory identity" in text
    assert "NOXA has quote assets without canonical pricing" in text
    assert "NOXA shard has unpriced points" in text


def test_noxa_coverage_validates_complete_row_without_mutating_ledger():
    text = WORKFLOW.read_text()

    assert "apply_phase2_source_coverage_report" in text
    assert '"coverage_status": "complete"' in text
    assert '"source_id": "noxa"' in text
    assert "noxa-source-coverage-report.json" in text
    assert "noxa-source-coverage-validation.json" in text
    assert "expected_source_id: noxa" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "git commit" not in text
    assert "git push" not in text
    assert "contents: write" not in text
