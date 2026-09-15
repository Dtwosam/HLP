from pathlib import Path


def _pricing_workflow() -> str:
    return Path(
        ".github/workflows/phase1-pons-pricing-eligibility-chain.yml"
    ).read_text()


def test_v2_eligibility_ignores_intentional_skipped_fallback_ancestors():
    content = _pricing_workflow()
    block = content.split("\n  v2_eligibility:\n", 1)[1].split(
        "\n  eligible_universe:\n", 1
    )[0]

    assert (
        "if: ${{ always() && needs.quote_fallback.result == 'success' }}"
        in block
    )


def test_eligible_universe_ignores_intentional_skipped_fallback_ancestors():
    content = _pricing_workflow()
    block = content.split("\n  eligible_universe:\n", 1)[1]

    assert (
        "if: ${{ always() && needs.v1_eligibility.result == 'success' && "
        "needs.v2_eligibility.result == 'success' }}"
        in block
    )
