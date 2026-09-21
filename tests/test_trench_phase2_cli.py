import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
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
        "--out", "registry.jsonl",
    ])
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
        out=str(out),
    )
    assert cmd_rpc_trench_registry_window(args) == 0
    assert observed == {"token": TOKEN, "block": 15}
    row = json.loads(out.read_text().strip())
    assert row["supply_raw"] == 123_000_000
    assert row["token_decimals"] == 9
