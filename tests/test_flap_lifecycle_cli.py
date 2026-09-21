import json

from hlp.cli import (
    build_parser,
    cmd_phase2_flap_graduation_markets,
    cmd_phase2_flap_v3_graduation_registry,
)


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


def test_flap_v3_graduation_registry_parser():
    args = build_parser().parse_args([
        "phase2-flap-v3-graduation-registry",
        "--registry", "flap.jsonl",
        "--handoffs", "handoffs.jsonl",
        "--out", "v3.jsonl",
        "--summary-out", "summary.json",
    ])
    assert args.handoffs == "handoffs.jsonl"

    market = build_parser().parse_args([
        "phase2-flap-v3-market-window",
        "--registry", "v3.jsonl",
        "--swaps", "swaps.jsonl",
        "--from-block", "10",
        "--to-block", "20",
        "--quote-decimals", "quotes.json",
        "--quote-feeds", "feeds.jsonl",
        "--out", "points.jsonl",
        "--summary-out", "summary.jsonl",
        "--report-out", "report.json",
    ])
    assert market.quote_feeds == "feeds.jsonl"


def test_flap_v3_graduation_registry_cli(tmp_path):
    token = "0x" + "11" * 20
    quote = "0x" + "22" * 20
    pool = "0x" + "33" * 20
    flap = tmp_path / "flap.jsonl"
    handoffs = tmp_path / "handoffs.jsonl"
    out = tmp_path / "v3.jsonl"
    summary = tmp_path / "summary.json"
    _write_jsonl(flap, [{
        "token": token,
        "launch_block": 10,
        "launch_transaction_hash": "0x" + "bb" * 32,
        "launch_transaction_index": 1,
        "launch_log_index": 0,
        "supply_raw": 1_000_000_000 * 10**18,
        "token_decimals": 18,
        "graduation_block": 20,
    }])
    _write_jsonl(handoffs, [{
        "token": token,
        "graduation_pool": pool,
        "graduation_quote_token": quote,
        "graduation_block": 20,
        "graduation_transaction_hash": "0x" + "aa" * 32,
        "graduation_transaction_index": 2,
        "graduation_log_index": 5,
        "market_handoff_complete": True,
        "market_available_at_graduation": True,
        "market_source_id": "direct_uniswap_v3",
        "market_venue": "uniswap_v3",
        "market_quote_decimals": 18,
        "market_initialize_block": 20,
        "market_initialize_transaction_index": 2,
        "market_initialize_log_index": 3,
        "market_initial_sqrt_price_x96": 2**96,
        "market_initial_tick": 0,
    }])

    args = build_parser().parse_args([
        "phase2-flap-v3-graduation-registry",
        "--registry", str(flap),
        "--handoffs", str(handoffs),
        "--out", str(out),
        "--summary-out", str(summary),
    ])
    assert cmd_phase2_flap_v3_graduation_registry(args) == 0
    row = json.loads(out.read_text().strip())
    assert row["lifecycle_log_index"] == 5
    report = json.loads(summary.read_text())
    assert report["graduated_tokens"] == 1
    assert report["source_coverage_complete"] is False

