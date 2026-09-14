from pathlib import Path


def test_pricing_chain_freezes_and_validates_v4_checkpoint():
    content = Path(
        ".github/workflows/phase1-pons-pricing-eligibility-chain.yml"
    ).read_text()

    assert content.count("v4_fallback_run_id:") >= 2
    assert content.count('default: "34754839901"') >= 2
    assert "V4_FALLBACK_RUN_ID: ${{ inputs.v4_fallback_run_id }}" in content
    assert "phase1-pons-v4-quote-fallback-salvage-one-shot.yml" in content
    assert '"phase1-pons-v4-quote-fallback-full"' in content


def test_pricing_chain_skips_v4_acquisition_and_reuses_checkpoint():
    content = Path(
        ".github/workflows/phase1-pons-pricing-eligibility-chain.yml"
    ).read_text()

    assert "inputs.v4_fallback_run_id == ''" in content
    assert "inputs.v4_fallback_run_id != ''" in content
    assert (
        "v4_run_id: ${{ inputs.v4_fallback_run_id != '' && "
        "inputs.v4_fallback_run_id || format('{0}', github.run_id) }}"
        in content
    )
    assert "needs.v4_checkpoint.result == 'success'" in content


def test_recovered_completion_inherits_pricing_v4_checkpoint_default():
    content = Path(
        ".github/workflows/phase1-pons-recovered-completion-chain.yml"
    ).read_text()

    pricing = content.split("\n  pricing:\n", 1)[1].split(
        "\n  promote_repaired_pricing:\n", 1
    )[0]
    assert "uses: ./.github/workflows/phase1-pons-pricing-eligibility-chain.yml" in pricing
    assert "v3_fallback_run_id: ${{ inputs.v3_fallback_run_id }}" in pricing
    assert "v4_fallback_run_id:" not in pricing
