from types import SimpleNamespace

import hlp.data.quote_causality as qc


FEED = "0x" + "11" * 20
AGG = "0x" + "22" * 20
TOKEN = "0x" + "33" * 20


class FakeRpc:
    def get_code(self, address, block):
        assert block == 99
        return "0x6000"


def test_quote_causality_uses_state_before_first_launch(monkeypatch):
    monkeypatch.setattr(qc, "read_chainlink_aggregator", lambda rpc, feed, block: AGG)
    monkeypatch.setattr(
        qc,
        "read_chainlink_latest_round",
        lambda rpc, feed, block: SimpleNamespace(
            description="Robinhood NVDA / USD",
            round_id=7,
            updated_at=1234,
            answer=250,
        ),
    )
    rows = qc.audit_pons_quote_causality(
        FakeRpc(),
        [{
            "pricing_status": "priced_chainlink_stock_token",
            "quote_token": TOKEN,
            "symbol": "NVDA",
            "feed": FEED,
            "directory_name": "Robinhood NVDA / USD",
            "first_launch_block": 100,
        }],
    )
    assert rows[0]["causal_state_block"] == 99
    assert rows[0]["aggregator"] == AGG
    assert rows[0]["causal_ready"] is True
    assert rows[0]["usd_price"] == "250"


def test_quote_causality_preserves_failure(monkeypatch):
    class NoCodeRpc:
        def get_code(self, address, block):
            return "0x"

    rows = qc.audit_pons_quote_causality(
        NoCodeRpc(),
        [{
            "pricing_status": "priced_chainlink_stock_token",
            "quote_token": TOKEN,
            "symbol": "NVDA",
            "feed": FEED,
            "first_launch_block": 100,
        }],
    )
    assert rows[0]["causal_ready"] is False
    assert "no code" in rows[0]["error"]



def test_quote_causality_includes_verified_crypto_chainlink_quotes(monkeypatch):
    monkeypatch.setattr(qc, "read_chainlink_aggregator", lambda rpc, feed, block: AGG)
    monkeypatch.setattr(
        qc,
        "read_chainlink_latest_round",
        lambda rpc, feed, block: SimpleNamespace(
            description="CBBTC / USD",
            round_id=8,
            updated_at=1235,
            answer=77557,
        ),
    )
    rows = qc.audit_pons_quote_causality(
        FakeRpc(),
        [{
            "pricing_status": "priced_chainlink_crypto_token",
            "quote_token": TOKEN,
            "symbol": "CBBTC",
            "feed": FEED,
            "directory_name": "CBBTC / USD",
            "first_launch_block": 100,
        }],
    )
    assert rows[0]["causal_ready"] is True
    assert rows[0]["description"] == "CBBTC / USD"
