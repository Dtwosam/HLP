from hlp.data.pons_v1 import PonsV1ConfigTimeline, enrich_v1_launch
from hlp.data.types import PonsLaunch, PonsV1LaunchConfig


PAIR = "0x" + "11" * 20
TOKEN = "0x" + "22" * 20
DEPLOYER = "0x" + "33" * 20
POOL = "0x" + "44" * 20


def config(*, supply, block, tx=0, log=0, action="added"):
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
    )


def launch(*, block, tx=0, log=0):
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
