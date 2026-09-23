from hlp.data.trench_registry import (
    attach_trench_launch_static_states,
    build_trench_launch_registry,
    build_trench_launch_registry_ordered,
)
from hlp.data.types import TrenchEvent
from hlp.protocols.erc20 import Erc20StaticState


TOKEN = "0x" + "11" * 20
CURVE = "0x" + "22" * 20
CREATOR = "0x" + "33" * 20
ZERO = "0x" + "00" * 20


def test_build_trench_registry():
    event = TrenchEvent(
        event_type="token_create",
        token=TOKEN,
        actor=CREATOR,
        curve=CURVE,
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
        token_uri="ipfs://cat",
        timestamp=123,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )
    rows = build_trench_launch_registry([event])
    assert len(rows) == 1
    row = rows[0]
    assert row["token"] == TOKEN
    assert row["curve"] == CURVE
    assert row["quote_token"] == ZERO
    assert row["supply_raw"] is None
    assert row["token_decimals"] is None



def test_trench_registry_freezes_limit_reach_order():
    create = TrenchEvent(
        event_type="token_create",
        token=TOKEN,
        actor=CREATOR,
        curve=CURVE,
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
        token_uri="ipfs://cat",
        timestamp=123,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )
    limit = TrenchEvent(
        **{
            field: getattr(create, field)
            for field in create.__dataclass_fields__
        }
    )
    object.__setattr__(limit, "event_type", "limit_reach")
    object.__setattr__(limit, "block_number", 20)
    object.__setattr__(limit, "log_index", 4)
    rows = build_trench_launch_registry([limit, create])
    assert rows[0]["limit_reach_block"] == 20
    assert rows[0]["limit_reach_log_index"] == 4


def test_attach_trench_launch_static_state():
    event = TrenchEvent(
        event_type="token_create",
        token=TOKEN,
        actor=CREATOR,
        curve=CURVE,
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
        token_uri="ipfs://cat",
        timestamp=123,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )
    rows = attach_trench_launch_static_states(
        build_trench_launch_registry([event]),
        [
            Erc20StaticState(
                token=TOKEN,
                block_number=10,
                decimals=9,
                total_supply=123_000_000,
            )
        ],
    )
    assert rows[0]["token_decimals"] == 9
    assert rows[0]["supply_raw"] == 123_000_000
    assert rows[0]["state_block"] == 10

