from types import SimpleNamespace

from hlp.config import ROBINHOOD_USDG
from hlp.data.quote_v4_routes import _address_topic, probe_v4_usdg_routes
from hlp.protocols.uniswap import V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC


TOKEN = "0x" + "11" * 20
POOL_ID = "0x" + "aa" * 32


def test_address_topic_pads_to_bytes32():
    topic = _address_topic(TOKEN)
    assert len(topic) == 66
    assert topic.endswith(TOKEN[2:])


def test_probe_with_no_initialize_is_explicitly_unresolved():
    calls = []

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            calls.append((start, end, kwargs))
            return iter(())

    rows = probe_v4_usdg_routes(
        Rpc(),
        [{
            "pricing_status": "missing_chainlink_feed",
            "quote_token": TOKEN,
            "symbol": "TEST",
            "quote_decimals": 18,
            "first_launch_block": 1000,
            "launches": 3,
            "versions": {"v2": 3},
        }],
        snapshot_head=2000,
        lookaround_blocks=100,
    )

    assert len(rows) == 1
    assert rows[0]["search_from_block"] == 900
    assert rows[0]["search_to_block"] == 1100
    assert rows[0]["initialize_events"] == 0
    assert rows[0]["causal_route_ready"] is False
    assert rows[0]["delayed_route_ready"] is False
    topics = calls[0][2]["topics"]
    assert topics[0] == V4_INITIALIZE_TOPIC
    assert topics[1] is None
    assert topics[2] in {_address_topic(TOKEN), _address_topic(ROBINHOOD_USDG)}
    assert topics[3] in {_address_topic(TOKEN), _address_topic(ROBINHOOD_USDG)}
