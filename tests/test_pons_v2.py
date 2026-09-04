from hlp.data.pons_v2 import ZERO_ADDRESS, iter_enriched_v2_launches
from hlp.data.types import (
    PonsV2LaunchConfig,
    PonsV2PairEconomics,
    RawLog,
)
from hlp.protocols.pons import (
    V2_PAIR_TOKEN_ECONOMICS_UPDATED_TOPIC,
    V2_TOKEN_LAUNCHED_TOPIC,
)


FACTORY = "0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e"
TOKEN = "0x" + "11" * 20
CURVE = "0x" + "22" * 20
DEPLOYER = "0x" + "33" * 20
PAIR = "0x" + "44" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def addr_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


def topic_addr(address: str) -> str:
    return "0x" + addr_word(address)


def launch_log(pair_token: str, threshold: int):
    return RawLog(
        chain_id=4663,
        block_number=20,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=2,
        log_index=0,
        address=FACTORY,
        topics=(
            V2_TOKEN_LAUNCHED_TOPIC,
            topic_addr(TOKEN),
            topic_addr(CURVE),
            topic_addr(DEPLOYER),
        ),
        data="0x" + addr_word(pair_token) + word(3) + word(threshold),
        removed=False,
    )


def cfg(phantom=5 * 10**18, threshold=50 * 10**18):
    return PonsV2LaunchConfig(
        action="bootstrap",
        config_id=3,
        supply=1_000_000_000 * 10**18,
        curve_fee_bps=100,
        phantom_quote=phantom,
        graduation_threshold=threshold,
        pool_fee=0,
        tick_spacing=60,
        enabled=True,
        block_number=10,
        transaction_hash="0x" + "00" * 32,
        transaction_index=None,
        log_index=-1,
    )


def test_native_v2_launch_uses_config_economics():
    rows = list(
        iter_enriched_v2_launches(
            [launch_log(ZERO_ADDRESS, 50 * 10**18)],
            bootstrap_configs=[cfg()],
        )
    )
    assert len(rows) == 1
    assert rows[0]["supply_raw"] == 1_000_000_000 * 10**18
    assert rows[0]["phantom_quote"] == 5 * 10**18
    assert rows[0]["quote_decimals"] == 18
    assert rows[0]["economics_source"] == "native_launch_config"


def test_erc20_v2_launch_uses_pair_economics():
    economics = PonsV2PairEconomics(
        pair_token=PAIR,
        phantom_quote=5_000_000,
        graduation_threshold=50_000_000,
        decimals=6,
        block_number=10,
        transaction_hash="0x" + "00" * 32,
        transaction_index=None,
        log_index=-1,
    )
    rows = list(
        iter_enriched_v2_launches(
            [launch_log(PAIR, 50_000_000)],
            bootstrap_configs=[cfg()],
            bootstrap_pair_economics=[economics],
        )
    )
    assert rows[0]["phantom_quote"] == 5_000_000
    assert rows[0]["quote_decimals"] == 6
    assert rows[0]["economics_source"] == "pair_token_economics"


def test_pair_economics_event_overrides_bootstrap_before_launch():
    update = RawLog(
        chain_id=4663,
        block_number=20,
        block_hash=None,
        transaction_hash="0x" + "bb" * 32,
        transaction_index=1,
        log_index=0,
        address=FACTORY,
        topics=(V2_PAIR_TOKEN_ECONOMICS_UPDATED_TOPIC, topic_addr(PAIR)),
        data="0x" + word(7_000_000) + word(70_000_000) + word(6),
        removed=False,
    )
    old = PonsV2PairEconomics(
        pair_token=PAIR,
        phantom_quote=5_000_000,
        graduation_threshold=50_000_000,
        decimals=6,
        block_number=10,
        transaction_hash="0x" + "00" * 32,
        transaction_index=None,
        log_index=-1,
    )
    rows = list(
        iter_enriched_v2_launches(
            [update, launch_log(PAIR, 70_000_000)],
            bootstrap_configs=[cfg()],
            bootstrap_pair_economics=[old],
        )
    )
    assert rows[0]["phantom_quote"] == 7_000_000
    assert rows[0]["graduation_threshold"] == 70_000_000
