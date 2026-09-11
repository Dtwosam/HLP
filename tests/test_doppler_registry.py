from hlp.data.doppler_registry import build_doppler_v4_registry
from hlp.data.types import DopplerLaunch


TOKEN="0x"+"11"*20
QUOTE="0x"+"22"*20
POOL_ID="0x"+"33"*32
TX="0x"+"aa"*32


def test_doppler_registry_uses_same_tx_currency_pair():
    launch=DopplerLaunch(
        asset=TOKEN,
        numeraire=QUOTE,
        initializer="0x"+"44"*20,
        pool_or_hook=TOKEN,
        block_number=10,
        transaction_hash=TX,
        transaction_index=1,
        log_index=2,
    )
    init={
        "pool_id":POOL_ID,
        "currency0":TOKEN,
        "currency1":QUOTE,
        "fee":10000,
        "tick_spacing":200,
        "hooks":"0x"+"44"*20,
        "sqrt_price_x96":2**96,
        "tick":0,
        "block_number":10,
        "transaction_hash":TX,
        "transaction_index":1,
        "log_index":3,
    }
    rows=build_doppler_v4_registry(
        [launch],[init],supply_raw_by_asset={TOKEN:10**27}
    )
    assert len(rows)==1
    assert rows[0]["pool_id"]==POOL_ID
    assert rows[0]["supply_raw"]==10**27
    assert rows[0]["pool_or_hook"]==TOKEN
