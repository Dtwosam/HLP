from hlp.data.pons_v1 import PonsV1ConfigTimeline, enrich_v1_launch, iter_enriched_v1_launches
from hlp.data.types import PonsLaunch, PonsV1LaunchConfig


PAIR = "0x" + "11" * 20
TOKEN = "0x" + "22" * 20
DEPLOYER = "0x" + "33" * 20
POOL = "0x" + "44" * 20
PRIMARY_FACTORY = "0xa5aab3f0c6eeadf30ef1d3eb997108e976351feb"
LEGACY_FACTORY = "0x0c37a24f5d23a486fa692d1500881d698b1f77a4"


def config(*, supply, block, tx=0, log=0, action="added", factory=None):
    return PonsV1LaunchConfig(
        action=action,
        config_id=7,
        pair_token=PAIR,
        graduation_threshold=100,
        initial_tick=120,
        supply=supply,
        max_wallet_bps=200,
        max_tx_bps=220,
        restriction_blocks=10,
        reserved_fee=0,
        enabled=True,
        router_requires_deadline=False,
        block_number=block,
        transaction_hash="0x" + f"{block:064x}",
        transaction_index=tx,
        log_index=log,
        factory=factory,
    )


def launch(*, block, tx=0, log=0, factory=None):
    return PonsLaunch(
        version="v1",
        token=TOKEN,
        deployer=DEPLOYER,
        pair_token=PAIR,
        block_number=block,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=tx,
        log_index=log,
        pool=POOL,
        launch_config_id=7,
        factory=factory,
    )


def test_timeline_uses_config_visible_at_exact_event_order():
    timeline = PonsV1ConfigTimeline(
        [
            config(supply=1_000, block=10, tx=1, log=0),
            config(supply=2_000, block=20, tx=2, log=0, action="updated"),
        ]
    )
    assert timeline.at_launch(launch(block=15)).supply == 1_000
    # Same-block launch before update still uses old config.
    assert timeline.at_launch(launch(block=20, tx=1, log=5)).supply == 1_000
    # Same-block launch after update uses new config.
    assert timeline.at_launch(launch(block=20, tx=3, log=0)).supply == 2_000


def test_enrichment_freezes_supply_and_18_decimals():
    timeline = PonsV1ConfigTimeline([config(supply=123456, block=1)])
    row = enrich_v1_launch(launch(block=2), timeline)
    assert row["supply_raw"] == 123456
    assert row["token_decimals"] == 18
    assert row["config_pair_token"] == PAIR



def test_stream_registry_applies_config_before_same_block_launch(monkeypatch):
    from hlp.data.types import RawLog
    from hlp.protocols.pons import (
        V1_LAUNCH_CONFIG_ADDED_TOPIC,
        V1_TOKEN_LAUNCHED_TOPIC,
    )

    def word(value):
        return f"{value:064x}"

    def addr_word(address):
        return address.removeprefix("0x").rjust(64, "0")

    config_log = RawLog(
        chain_id=4663,
        block_number=10,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=0,
        address="0xa5aab3f0c6eeadf30ef1d3eb997108e976351feb",
        topics=(V1_LAUNCH_CONFIG_ADDED_TOPIC, "0x" + word(7)),
        data=(
            "0x"
            + addr_word(PAIR)
            + word(100)
            + word(120)
            + word(1_000_000_000 * 10**18)
            + word(200)
            + word(220)
            + word(10)
            + word(0)
            + word(1)
            + word(0)
        ),
        removed=False,
    )
    launch_log = RawLog(
        chain_id=4663,
        block_number=10,
        block_hash=None,
        transaction_hash="0x" + "bb" * 32,
        transaction_index=2,
        log_index=0,
        address="0xa5aab3f0c6eeadf30ef1d3eb997108e976351feb",
        topics=(
            V1_TOKEN_LAUNCHED_TOPIC,
            "0x" + addr_word(TOKEN),
            "0x" + addr_word(DEPLOYER),
            "0x" + addr_word("0x" + "55" * 20),
        ),
        data=(
            "0x"
            + addr_word(PAIR)
            + addr_word(POOL)
            + word(0)
            + word(7)
            + word(123)
            + word(20)
            + word(0)
        ),
        removed=False,
    )
    rows = list(iter_enriched_v1_launches([config_log, launch_log]))
    assert len(rows) == 1
    assert rows[0]["supply_raw"] == 1_000_000_000 * 10**18
    assert rows[0]["dex_factory"] == "0x" + "55" * 20



def test_timeline_scopes_same_config_id_by_factory():
    timeline = PonsV1ConfigTimeline(
        [
            config(supply=1_000, block=10, factory=PRIMARY_FACTORY),
            config(supply=9_000, block=10, factory=LEGACY_FACTORY),
        ]
    )
    assert timeline.at_launch(
        launch(block=20, factory=PRIMARY_FACTORY)
    ).supply == 1_000
    assert timeline.at_launch(
        launch(block=20, factory=LEGACY_FACTORY)
    ).supply == 9_000
