from hlp.data.hood_fun_registry import build_hood_fun_launch_registry
from hlp.data.types import HoodFunEvent


TOKEN = "0x" + "11" * 20


def launch(curve_inventory=800_000_000 * 10**18):
    return HoodFunEvent(
        event_type="token_created",
        token=TOKEN,
        actor="0x" + "22" * 20,
        is_buy=None,
        quote_amount_raw=None,
        token_amount_raw=None,
        fee_raw=None,
        virtual_quote_raw=2_810_000_000_000_000_000,
        virtual_token_raw=1_145_000_000 * 10**18,
        curve_inventory_raw=curve_inventory,
        name="Cat",
        symbol="CAT",
        metadata_uri="ipfs://cat",
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=0,
    )


def test_hood_fun_registry_derives_configurable_supply_from_80pct_curve_inventory():
    rows = build_hood_fun_launch_registry([launch()])
    assert len(rows) == 1
    row = rows[0]
    assert row["supply_raw"] == 1_000_000_000 * 10**18
    assert row["curve_inventory_raw"] == 800_000_000 * 10**18


def test_hood_fun_registry_scales_arbitrary_supply():
    rows = build_hood_fun_launch_registry([launch(8 * 10**17)])
    assert rows[0]["supply_raw"] == 10**18
