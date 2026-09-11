from hlp.data.pons_time import (
    enrich_pons_episodes_with_time,
    enrich_pons_points_with_time,
    fetch_block_timestamp_rows,
)


class FakeRpc:
    def get_blocks_batched(
        self,
        blocks,
        *,
        full_transactions=False,
        batch_size=100,
        min_batch_size=1,
    ):
        assert blocks == [10, 11]
        return [
            {"number": hex(10), "hash": "0x" + "aa" * 32, "timestamp": hex(1000)},
            {"number": hex(11), "hash": "0x" + "bb" * 32, "timestamp": hex(1007)},
        ]


def test_fetch_and_enrich_pons_timestamps():
    timestamp_rows = fetch_block_timestamp_rows(FakeRpc(), [11, 10, 11])
    assert [row["block_number"] for row in timestamp_rows] == [10, 11]

    points = [
        {
            "token": "0x" + "11" * 20,
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 0,
        },
        {
            "token": "0x" + "11" * 20,
            "block_number": 11,
            "transaction_index": 1,
            "log_index": 0,
        },
    ]
    enriched = enrich_pons_points_with_time(points, timestamp_rows)
    assert enriched[0]["seconds_since_first_priced_point"] == 0
    assert enriched[1]["seconds_since_first_priced_point"] == 7

    episodes = [{
        "token": "0x" + "11" * 20,
        "episode_index": 0,
        "peak_block": 10,
        "drawdown_start_block": 10,
        "trough_block": 11,
        "recovery_block": None,
    }]
    ep = enrich_pons_episodes_with_time(episodes, timestamp_rows)[0]
    assert ep["peak_to_trough_seconds"] == 7
    assert ep["trough_to_recovery_seconds"] is None
