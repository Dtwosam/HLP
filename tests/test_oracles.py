from hlp.data.oracles import merge_oracle_updates


def test_merge_oracle_updates_preserves_global_event_order():
    rows = merge_oracle_updates(
        [
            [
                {
                    "quote_token": "0x" + "11" * 20,
                    "block_number": 10,
                    "transaction_index": 3,
                    "log_index": 0,
                }
            ],
            [
                {
                    "quote_token": "0x" + "22" * 20,
                    "block_number": 10,
                    "transaction_index": 1,
                    "log_index": 5,
                },
                {
                    "quote_token": "0x" + "22" * 20,
                    "block_number": 11,
                    "transaction_index": 0,
                    "log_index": 0,
                },
            ],
        ]
    )
    assert [
        (r["block_number"], r["transaction_index"], r["log_index"])
        for r in rows
    ] == [(10, 1, 5), (10, 3, 0), (11, 0, 0)]


def test_staggered_oracles_use_individual_activation_blocks(monkeypatch):
    from types import SimpleNamespace
    import hlp.data.oracles as module

    agg1 = "0x" + "a1" * 20
    agg2 = "0x" + "a2" * 20
    feed1 = "0x" + "b1" * 20
    feed2 = "0x" + "b2" * 20

    def aggregator(rpc, feed, block):
        return agg1 if feed == feed1 else agg2

    def latest(rpc, feed, block):
        symbol = "AAA" if feed == feed1 else "BBB"
        round_id = 10 if feed == feed1 else 20
        return SimpleNamespace(
            round_id=round_id,
            updated_at=1000,
            decimals=8,
            answer=250,
            description=f"Robinhood {symbol} / USD",
        )

    monkeypatch.setattr(module, "read_chainlink_aggregator", aggregator)
    monkeypatch.setattr(module, "read_chainlink_latest_round", latest)
    monkeypatch.setattr(
        module,
        "decode_chainlink_answer_updated",
        lambda raw: raw.event,
    )

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            assert start == 100
            assert end == 300
            assert kwargs["address"] == [agg1, agg2]
            return iter([
                SimpleNamespace(
                    address=agg2,
                    block_number=150,
                    event=SimpleNamespace(
                        round_id=21,
                        answer_raw=26_000_000_000,
                        updated_at=1100,
                        block_number=150,
                        transaction_hash="0x" + "11" * 32,
                        transaction_index=1,
                        log_index=0,
                    ),
                ),
                SimpleNamespace(
                    address=agg1,
                    block_number=160,
                    event=SimpleNamespace(
                        round_id=11,
                        answer_raw=25_500_000_000,
                        updated_at=1200,
                        block_number=160,
                        transaction_hash="0x" + "22" * 32,
                        transaction_index=1,
                        log_index=0,
                    ),
                ),
                SimpleNamespace(
                    address=agg2,
                    block_number=210,
                    event=SimpleNamespace(
                        round_id=21,
                        answer_raw=26_000_000_000,
                        updated_at=1300,
                        block_number=210,
                        transaction_hash="0x" + "33" * 32,
                        transaction_index=1,
                        log_index=0,
                    ),
                ),
            ])

    states, updates = module.reconstruct_staggered_chainlink_usd_tapes(
        Rpc(),
        feeds=[
            {
                "quote_token": "0x" + "01" * 20,
                "symbol": "AAA",
                "feed": feed1,
                "first_launch_block": 100,
            },
            {
                "quote_token": "0x" + "02" * 20,
                "symbol": "BBB",
                "feed": feed2,
                "first_launch_block": 200,
            },
        ],
        to_block=300,
    )
    rows = list(updates)
    assert [row["symbol"] for row in states] == ["AAA", "BBB"]
    assert [row["symbol"] for row in rows] == ["AAA", "BBB"]
    assert rows[0]["block_number"] == 160
    assert rows[1]["block_number"] == 210
