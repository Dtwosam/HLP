import json
from types import SimpleNamespace

from hlp.cli import (
    build_parser,
    cmd_rpc_pools_trade_lbp_initializer_tape,
)
from hlp.data.types import PoolsTradeLbpInitializerCreated
from hlp.protocols.erc20 import Erc20StaticState


TOKEN = "0x" + "11" * 20


class FakeRpc:
    route_label = "test_archive"
    requests_made = 2
    response_bytes_received = 100

    def assert_robinhood(self):
        return None

    def iter_logs_chunked(self, *args, **kwargs):
        return [object()]


def initializer():
    return PoolsTradeLbpInitializerCreated(
        strategy="0x05d552391067389ee44fec3924157ed33f976000",
        initializer="0x" + "22" * 20,
        token=TOKEN,
        currency="0x" + "00" * 20,
        migration_block=20,
        reserved_token_amount_for_lp=200,
        recipient="0x" + "33" * 20,
        position_recipient="0x" + "44" * 20,
        pool_fee=2500,
        pool_tick_spacing=50,
        pool_hook="0x" + "00" * 20,
        position_definitions_offset=352,
        lp_allocation_schedule_offset=576,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )


def test_lbp_initializer_parser_accepts_state_out():
    args = build_parser().parse_args([
        "rpc-pools-trade-lbp-initializer-tape",
        "--from-block", "10",
        "--to-block", "20",
        "--out", "initializers.jsonl",
        "--state-out", "state.jsonl",
    ])
    assert args.state_out == "state.jsonl"


def test_lbp_registry_parser_accepts_states():
    args = build_parser().parse_args([
        "pools-trade-lbp-registry",
        "--created", "created.jsonl",
        "--distributed", "distributed.jsonl",
        "--initializers", "initializers.jsonl",
        "--states", "state.jsonl",
        "--out", "registry.jsonl",
    ])
    assert args.states == "state.jsonl"


def test_lbp_initializer_tape_freezes_exact_block_state(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr("hlp.cli._archive_rpc", lambda args: FakeRpc())
    monkeypatch.setattr(
        "hlp.cli.decode_pools_trade_lbp_initializer_created",
        lambda raw: initializer(),
    )
    observed = {}

    def fake_static(rpc, token, *, block):
        observed["token"] = token
        observed["block"] = block
        return Erc20StaticState(
            token=token,
            block_number=block,
            decimals=18,
            total_supply=1000,
        )

    monkeypatch.setattr("hlp.cli.read_erc20_static", fake_static)
    init_path = tmp_path / "initializers.jsonl"
    state_path = tmp_path / "state.jsonl"
    args = SimpleNamespace(
        from_block=10,
        to_block=20,
        chunk_size=200,
        min_chunk_size=25,
        out=str(init_path),
        state_out=str(state_path),
    )

    assert cmd_rpc_pools_trade_lbp_initializer_tape(args) == 0
    assert observed == {"token": TOKEN, "block": 10}
    state = json.loads(state_path.read_text().strip())
    assert state == {
        "token": TOKEN,
        "state_block": 10,
        "token_decimals": 18,
        "supply_raw": 1000,
    }
