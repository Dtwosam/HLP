import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text()


def _embedded_python_blocks(content: str) -> list[str]:
    lines = content.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() != "python - <<'PY'":
            index += 1
            continue
        indent = len(line) - len(line.lstrip())
        body: list[str] = []
        index += 1
        while index < len(lines):
            current = lines[index]
            current_indent = len(current) - len(current.lstrip())
            if current.strip() == "PY" and current_indent == indent:
                break
            body.append(current[indent:] if len(current) >= indent else current.lstrip())
            index += 1
        else:
            raise AssertionError("unterminated embedded Python heredoc")
        blocks.append("\n".join(body) + "\n")
        index += 1
    return blocks


def test_recovered_completion_config_carries_repaired_pricing_sources():
    config = json.loads(
        (ROOT / ".github" / "phase1-pons-recovered-completion.json").read_text()
    )
    assert config["repaired_v2_lifecycle_run_id"] == 0
    assert config["repaired_v4_fallback_run_id"] == 0
    assert config["validation_generation"] == 8


def test_recovered_completion_one_shot_wires_repaired_pricing_mode_fail_closed():
    content = _workflow("phase1-pons-recovered-completion-one-shot.yml")
    required = (
        "repaired_v2_lifecycle_run_id",
        "repaired_v4_fallback_run_id",
        "repaired pricing run IDs must be supplied together",
        "repaired pricing cannot be combined with pricing_run_id",
        "validation_generation != 8",
    )
    for needle in required:
        assert needle in content, needle


def test_recovered_completion_chain_routes_repaired_pricing_without_reacquisition():
    content = _workflow("phase1-pons-recovered-completion-chain.yml")
    required = (
        "repaired_v2_lifecycle_run_id",
        "repaired_v4_fallback_run_id",
        "promote_repaired_pricing:",
        "phase1-pons-repaired-pricing-promote.yml",
        "repaired pricing run IDs must be supplied together",
        "repaired pricing cannot be combined with pricing_run_id",
    )
    for needle in required:
        assert needle in content, needle

    pricing_job = content.split("\n  pricing:\n", 1)[1].split("\n  ", 1)[0]
    assert "repaired_v2_lifecycle_run_id" in pricing_job
    assert "repaired_v4_fallback_run_id" in pricing_job
    assert "== ''" in pricing_job

    assert "source_eligibility_run_id: ${{ github.run_id }}" in content
    assert "needs.promote_repaired_pricing.result == 'success'" in content


def test_repaired_pricing_promotion_is_exact_artifact_only_and_causal():
    content = _workflow("phase1-pons-repaired-pricing-promote.yml")
    required = (
        "34900105493",
        "34894335995",
        "34480161440",
        "34228430753",
        "34471480180",
        "279d8016b1f62aef01167650be3cc70e0ca72f6c",
        "09c788e6321b958d1fb78f00e3330605e86435e9",
        "db374769984c621d4f2f22aad27e0686f218164a",
        "10154428836",
        "10186898865",
        "10370673267",
        "10368788172",
        "10368454044",
        "phase1-pons-v1-lifecycle-eligibility",
        "phase1-pons-v2-lifecycle-eligibility",
        "phase1-pons-v3-quote-fallback-full",
        "phase1-pons-v4-quote-fallback-full",
        "phase1-pons-quote-fallback-full",
        '"owned_quote_assets": 30',
        '"v3_routes": 25',
        '"v4_routes": 5',
        '"v4_causal_initial_assets": 5',
        '"v3_v4_overlap_assets": 0',
        '"eligibility_unknown_tokens": 0',
        '"updates": 806_561',
        "actions/download-artifact@v4",
        "actions/upload-artifact@v4",
    )
    for needle in required:
        assert needle in content, needle

    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "phase1-pons-pricing-eligibility-chain.yml" not in content
    assert "eth_getLogs" not in content
    blocks = _embedded_python_blocks(content)
    assert blocks
    for index, block in enumerate(blocks):
        compile(block, f"repaired-pricing-promote:{index}", "exec")
