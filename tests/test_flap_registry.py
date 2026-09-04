from hlp.data.flap_registry import build_flap_launch_registry
from hlp.data.types import FlapEvent


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20


def event(kind, *, logi, actor=None, value=None, value2=None, amount=None):
    return FlapEvent(
        event_type=kind,
        token=TOKEN,
        actor=actor,
        amount_raw=amount,
        quote_amount_raw=None,
        fee_raw=None,
        post_price_raw=None,
        value_raw=value,
        value2_raw=value2,
        pool=None,
        name="Cat" if kind == "token_created" else None,
        symbol="CAT" if kind == "token_created" else None,
        meta="ipfs://cat" if kind == "token_created" else None,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=logi,
    )


def test_build_flap_registry_from_creation_config_events():
    rows = build_flap_launch_registry(
        [
            event("token_created", logi=0, actor="0x" + "22" * 20, value=7),
            event("curve_set_v2", logi=1, value=1, value2=2, amount=3),
            event("dex_supply_thresh_set", logi=2, value=800),
            event("quote_set", logi=3, actor=ZERO),
            event("migrator_set", logi=4, value=1),
            event("token_version_set", logi=5, value=7),
            event("dex_preference_set", logi=6, value=2, value2=1),
        ]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["token"] == TOKEN
    assert row["quote_token"] == ZERO
    assert row["r"] == 1 and row["h"] == 2 and row["k"] == 3
    assert row["dex_supply_thresh_raw"] == 800
    assert row["migrator_type"] == 1
    assert row["dex_id"] == 2
    assert row["supply_raw"] == 1_000_000_000 * 10**18
