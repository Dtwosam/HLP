from hlp.data.trench_registry import build_trench_launch_registry
from hlp.data.types import TrenchEvent


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
    assert row["supply_raw"] == 1_000_000_000 * 10**18
