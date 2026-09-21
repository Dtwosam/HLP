import json

from hlp.cli import build_parser, cmd_phase2_flap_graduation_markets


def _write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )


def test_flap_graduation_market_parser_accepts_multiple_registries():
    args = build_parser().parse_args([
        "phase2-flap-graduation-markets",
        "--registry", "flap.jsonl",
        "--market-registry", "uniswap.jsonl",
        "--market-registry", "sushi.jsonl",
        "--out", "handoff.jsonl",
        "--summary-out", "summary.json",
    ])
    assert args.market_registry == ["uniswap.jsonl", "sushi.jsonl"]


def test_flap_graduation_market_cli_is_evidence_only(tmp_path):
    token = "0x" + "11" * 20
    quote = "0x" + "22" * 20
    pool = "0x" + "33" * 20
    flap = tmp_path / "flap.jsonl"
    market = tmp_path / "market.jsonl"
    out = tmp_path / "handoff.jsonl"
    summary = tmp_path / "summary.json"

    _write_jsonl(flap, [{
        "token": token,
        "graduation_block": 20,
        "graduation_transaction_hash": "0x" + "aa" * 32,
        "graduation_transaction_index": 2,
        "graduation_log_index": 5,
        "graduation_pool": pool,
        "graduation_quote_token": quote,
        "graduation_dex_id": 2,
        "graduation_lp_fee_profile": 1,
    }])
    _write_jsonl(market, [{
        "source_id": "direct_uniswap_v3",
        "venue": "uniswap_v3",
        "source_kind": "direct_dex",
        "token": token,
        "quote_token": quote,
        "quote_decimals": 18,
        "pool": pool,
        "initialize_block": 20,
        "initialize_transaction_index": 2,
        "initialize_log_index": 3,
        "initial_sqrt_price_x96": 2**96,
        "initial_tick": 0,
    }])

    args = build_parser().parse_args([
        "phase2-flap-graduation-markets",
        "--registry", str(flap),
        "--market-registry", str(market),
        "--out", str(out),
        "--summary-out", str(summary),
    ])
    assert cmd_phase2_flap_graduation_markets(args) == 0
    report = json.loads(summary.read_text())
    assert report["matched_address_markets"] == 1
    assert report["all_graduations_resolved"] is True
    assert report["source_coverage_complete"] is False
