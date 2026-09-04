import html

import pytest

from hlp.data.chainlink_directory import (
    ChainlinkDirectoryClient,
    ChainlinkDirectoryError,
)


def record(symbol, proxy, *, chain="Robinhood", heartbeat=86400):
    return (
        f'"heartbeat":[0,{heartbeat}],'
        f'"history":[0,null],'
        f'"name":[0,"Robinhood {symbol} / USD"],'
        f'"path":[0,"robinhood-{symbol.lower()}-usd-shared-svr"],'
        f'"proxyAddress":[0,"{proxy}"],'
        f'"secondaryProxyAddress":[0,"0x{"22" * 20}"],'
        f'"docs":[0,{{"blockchainName":[0,"{chain}"]}}],'
    )


def test_parse_exact_feed_from_html_escaped_payload():
    proxy = "0x" + "11" * 20
    page = html.unescape(
        html.escape(record("NVDA", proxy) + record("TSLA", "0x" + "33" * 20))
    )
    row = ChainlinkDirectoryClient.parse_robinhood_feed(page, "nvda")
    assert row.symbol == "NVDA"
    assert row.proxy_address == proxy
    assert row.heartbeat_seconds == 86400
    assert row.blockchain_name == "Robinhood"


def test_wrong_blockchain_fails_closed():
    page = record("NVDA", "0x" + "11" * 20, chain="Ethereum")
    with pytest.raises(ChainlinkDirectoryError):
        ChainlinkDirectoryClient.parse_robinhood_feed(page, "NVDA")



def test_parse_hyphenated_robinhood_feed_name():
    proxy = "0x" + "44" * 20
    page = (
        '"heartbeat":[0,86400],'
        '"history":[0,null],'
        '"name":[0,"Robinhood AMC-USD"],'
        '"path":[0,"robinhood-amc-usd-shared-svr"],'
        f'"proxyAddress":[0,"{proxy}"],'
        f'"secondaryProxyAddress":[0,"0x{"55" * 20}"],'
        '"docs":[0,{"blockchainName":[0,"Robinhood"]}],'
    )

    row = ChainlinkDirectoryClient.parse_robinhood_feed(page, "amc")

    assert row.symbol == "AMC"
    assert row.name == "Robinhood AMC-USD"
    assert row.proxy_address == proxy
