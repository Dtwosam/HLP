import pytest

from hlp.data.pons_holders import (
    ZERO_ADDRESS,
    fetch_pons_transfer_rows,
    reconstruct_pons_holder_states,
    summarize_pons_holder_states,
)
from hlp.data.types import RawLog
from hlp.protocols.erc20 import TRANSFER_TOPIC


TOKEN = "0x" + "11" * 20
A = "0x" + "aa" * 20
B = "0x" + "bb" * 20


def transfer(block, log_index, from_address, to_address, value):
    return {
        "token": TOKEN,
        "from_address": from_address,
        "to_address": to_address,
        "value_raw": value,
        "block_number": block,
        "transaction_hash": "0x" + f"{block * 100 + log_index:064x}",
        "transaction_index": 1,
        "log_index": log_index,
    }


def topic_address(address):
    return "0x" + address.removeprefix("0x").rjust(64, "0")


def test_holder_replay_tracks_mint_transfer_burn_and_zero_balances():
    rows = reconstruct_pons_holder_states([
        transfer(1, 0, ZERO_ADDRESS, A, 100),
        transfer(2, 0, A, B, 40),
        transfer(3, 0, B, ZERO_ADDRESS, 10),
        transfer(4, 0, A, B, 60),
    ])

    assert rows[0]["holder_count_after"] == 1
    assert rows[0]["accounted_supply_after_raw"] == 100
    assert rows[1]["holder_count_after"] == 2
    assert rows[2]["accounted_supply_after_raw"] == 90
    assert rows[3]["from_balance_after_raw"] == 0
    assert rows[3]["to_balance_after_raw"] == 90
    assert rows[3]["holder_count_after"] == 1

    summary = summarize_pons_holder_states(rows)
    assert summary == [{
        "token": TOKEN,
        "last_block_number": 4,
        "last_transaction_index": 1,
        "last_log_index": 0,
        "transfers": 4,
        "mints": 1,
        "burns": 1,
        "holder_count": 1,
        "accounted_supply_raw": 90,
    }]


def test_holder_replay_fails_closed_on_missing_initial_history():
    with pytest.raises(ValueError, match="debit exceeds known balance"):
        reconstruct_pons_holder_states([
            transfer(10, 0, A, B, 1),
        ])


def test_holder_replay_self_transfer_preserves_state():
    rows = reconstruct_pons_holder_states([
        transfer(1, 0, ZERO_ADDRESS, A, 100),
        transfer(2, 0, A, A, 40),
    ])
    assert rows[-1]["holder_count_after"] == 1
    assert rows[-1]["accounted_supply_after_raw"] == 100
    assert rows[-1]["from_balance_after_raw"] == 100
    assert rows[-1]["to_balance_after_raw"] == 100


def test_transfer_fetch_is_bounded_and_decodes_only_requested_tokens():
    raw = RawLog(
        chain_id=4663,
        block_number=10,
        block_hash=None,
        transaction_hash="0x" + "22" * 32,
        transaction_index=1,
        log_index=2,
        address=TOKEN,
        topics=(
            TRANSFER_TOPIC,
            topic_address(ZERO_ADDRESS),
            topic_address(A),
        ),
        data="0x" + f"{123:064x}",
        removed=False,
    )
    calls = []

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            calls.append((start, end, kwargs))
            return iter([raw])

    rows = list(
        fetch_pons_transfer_rows(
            Rpc(),
            [TOKEN, TOKEN],
            from_block=5,
            to_block=15,
            chunk_size=100,
            min_chunk_size=5,
        )
    )
    assert rows[0]["value_raw"] == 123
    assert calls == [(
        5,
        15,
        {
            "address": [TOKEN],
            "topics": [TRANSFER_TOPIC],
            "chunk_size": 100,
            "min_chunk_size": 5,
        },
    )]


def test_transfer_fetch_caps_representative_token_set():
    with pytest.raises(ValueError, match="capped at 50 tokens"):
        list(
            fetch_pons_transfer_rows(
                object(),
                [f"0x{i:040x}" for i in range(1, 52)],
                from_block=1,
                to_block=2,
            )
        )
