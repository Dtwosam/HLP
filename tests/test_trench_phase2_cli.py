import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_phase2_v4_registry_event_filter,
    cmd_rpc_trench_registry_window,
)
from hlp.data.types import TrenchEvent
from hlp.protocols.erc20 import Erc20StaticState


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20


class FakeRpc:
    route_label = "test_archive"
    requests_made = 3
    response_bytes_received = 100

    def assert_robinhood(self):
        return None

    def iter_logs_chunked(self, *args, **kwargs):
        return [object()]


def test_trench_phase2_registry_parser():
    args = build_parser().parse_args([
        "rpc-trench-registry-window",
        "--from-block", "10",
        "--to-block", "20",
        "--events-out", "events.jsonl",
        "--out", "registry.jsonl",
    ])
    assert args.events_out == "events.jsonl"
    assert args.from_block == 10
    assert args.to_block == 20


def test_trench_registry_window_reads_supply_at_launch_block(
    monkeypatch,
    tmp_path,
):
    event = TrenchEvent(
        event_type="token_create",
        token=TOKEN,
        actor="0x" + "22" * 20,
        curve="0x" + "33" * 20,
        quote_token=ZERO,
        amount_raw=None,
        quote_amount_raw=None,
        protocol_fee_raw=None,
        extra_fee_raw=None,
        extra_fee_receiver=None,
        extra_fee_rate=None,
        real_quote_reserves_raw=None,
        real_token_reserves_raw=None,
        virtual_quote_raw=None,
        virtual_token_raw=None,
        name="Cat",
        symbol="CAT",
        token_uri=None,
        timestamp=123,
        block_number=15,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )
    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr("hlp.cli.decode_trench_event", lambda raw: event)
    observed = {}

    def fake_static(rpc, token, *, block):
        observed["token"] = token
        observed["block"] = block
        return Erc20StaticState(
            token=token,
            block_number=block,
            decimals=9,
            total_supply=123_000_000,
        )

    monkeypatch.setattr("hlp.cli.read_erc20_static", fake_static)
    out = tmp_path / "registry.jsonl"
    args = SimpleNamespace(
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        events_out=None,
        out=str(out),
    )
    assert cmd_rpc_trench_registry_window(args) == 0
    assert observed == {"token": TOKEN, "block": 15}
    row = json.loads(out.read_text().strip())
    assert row["supply_raw"] == 123_000_000
    assert row["token_decimals"] == 9


def test_trench_handoff_market_registry_parser():
    parser = build_parser()
    args = parser.parse_args([
        "phase2-trench-handoff-market-registry",
        "--registry", "trench.jsonl",
        "--handoffs", "handoffs.jsonl",
        "--market-registry", "v3.jsonl",
        "--market-registry", "v4.jsonl",
        "--v3-out", "trench-v3.jsonl",
        "--v4-out", "trench-v4.jsonl",
        "--summary-out", "summary.json",
    ])

    assert args.registry == "trench.jsonl"
    assert args.handoffs == "handoffs.jsonl"
    assert args.market_registry == ["v3.jsonl", "v4.jsonl"]
    assert args.v3_out == "trench-v3.jsonl"
    assert args.v4_out == "trench-v4.jsonl"


def test_v4_registry_event_filter_parser():
    args = build_parser().parse_args([
        "phase2-v4-registry-event-filter",
        "--registry", "registry.jsonl",
        "--input", "swaps.jsonl",
        "--out", "filtered.jsonl",
        "--summary-out", "summary.json",
    ])
    assert args.registry == "registry.jsonl"
    assert args.input == "swaps.jsonl"
    assert args.input_manifest is None


def test_v4_registry_event_filter_keeps_only_registered_pool_id(tmp_path):
    pool_id = "0x" + "22" * 32
    other = "0x" + "33" * 32
    registry = tmp_path / "registry.jsonl"
    events = tmp_path / "events.jsonl"
    out = tmp_path / "filtered.jsonl"
    summary = tmp_path / "summary.json"
    registry.write_text(json.dumps({
        "pool_id": pool_id,
        "lifecycle_block": 10,
        "lifecycle_transaction_index": 1,
        "lifecycle_log_index": 2,
    }) + "\n")
    events.write_text(
        json.dumps({
            "pool_id": pool_id,
            "block_number": 11,
            "transaction_hash": "0x" + "aa" * 32,
            "transaction_index": 1,
            "log_index": 0,
        }) + "\n" +
        json.dumps({
            "pool_id": other,
            "block_number": 11,
            "transaction_hash": "0x" + "bb" * 32,
            "transaction_index": 1,
            "log_index": 1,
        }) + "\n"
    )

    args = SimpleNamespace(
        registry=str(registry),
        input=str(events),
        input_manifest=None,
        input_shard_dir=None,
        out=str(out),
        summary_out=str(summary),
    )
    assert cmd_phase2_v4_registry_event_filter(args) == 0
    rows = [
        json.loads(line)
        for line in out.read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["pool_id"] == pool_id
    report = json.loads(summary.read_text())
    assert report["records"] == 1
    assert report["matched_pool_ids"] == 1


def test_v4_registry_event_filter_rejects_same_block_prelifecycle_event(
    tmp_path,
):
    pool_id = "0x" + "22" * 32
    registry = tmp_path / "registry.jsonl"
    events = tmp_path / "events.jsonl"
    out = tmp_path / "filtered.jsonl"
    summary = tmp_path / "summary.json"
    registry.write_text(json.dumps({
        "pool_id": pool_id,
        "lifecycle_block": 10,
        "lifecycle_transaction_index": 1,
        "lifecycle_log_index": 2,
    }) + "\n")
    events.write_text(json.dumps({
        "pool_id": pool_id,
        "block_number": 10,
        "transaction_hash": "0x" + "aa" * 32,
        "transaction_index": 1,
        "log_index": 1,
    }) + "\n")

    args = SimpleNamespace(
        registry=str(registry),
        input=str(events),
        input_manifest=None,
        input_shard_dir=None,
        out=str(out),
        summary_out=str(summary),
    )
    try:
        cmd_phase2_v4_registry_event_filter(args)
    except ValueError as exc:
        assert "predates registry lifecycle" in str(exc)
    else:
        raise AssertionError("pre-lifecycle same-block V4 event was accepted")

