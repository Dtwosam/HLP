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
