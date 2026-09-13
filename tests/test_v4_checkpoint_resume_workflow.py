from pathlib import Path


def test_pricing_chain_can_resume_from_external_v4_checkpoint():
    content = Path(
        ".github/workflows/phase1-pons-pricing-eligibility-chain.yml"
    ).read_text()

    assert content.count("v4_fallback_run_id:") >= 2
    assert "inputs.v4_fallback_run_id == ''" in content
    assert "inputs.v4_fallback_run_id != ''" in content
    assert (
        "v4_run_id: ${{ inputs.v4_fallback_run_id != '' && "
        "inputs.v4_fallback_run_id || format('{0}', github.run_id) }}"
        in content
    )


def test_recovered_completion_validates_and_threads_v4_checkpoint():
    content = Path(
        ".github/workflows/phase1-pons-recovered-completion-chain.yml"
    ).read_text()

    assert content.count("v4_fallback_run_id:") >= 3
    assert "V4_FALLBACK_RUN_ID: ${{ inputs.v4_fallback_run_id }}" in content
    assert "phase1-pons-v4-quote-fallback-salvage-one-shot.yml" in content
    assert '"phase1-pons-v4-quote-fallback-full"' in content
    assert "v4_fallback_run_id: ${{ inputs.v4_fallback_run_id }}" in content


def test_recovered_one_shot_hands_off_v4_checkpoint_output():
    content = Path(
        ".github/workflows/phase1-pons-recovered-completion-one-shot.yml"
    ).read_text()

    assert "v4_fallback_run_id: ${{ steps.read.outputs.v4_fallback_run_id }}" in content
    assert '"v4_fallback_run_id",' in content
    assert 'v4_fallback_id = int(config.get("v4_fallback_run_id", 0))' in content
    assert 'output.write(f"v4_fallback_run_id={v4_fallback_id}\\n")' in content
    assert (
        "v4_fallback_run_id: ${{ needs.config.outputs.v4_fallback_run_id }}"
        in content
    )
