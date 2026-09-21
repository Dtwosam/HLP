import pytest

from hlp.data.direct_supply import (
    DirectSupplyTimeline,
    build_direct_supply_delta_rows,
)


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20
ALICE = "0x" + "22" * 20


def transfer(
    *,
    from_address,
    to_address,
    value,
    block,
    txi,
    logi,
):
    return {
        "token": TOKEN,
        "from_address": from_address,
        "to_address": to_address,
        "value_raw": value,
        "block_number": block,
        "transaction_hash": "0x" + f"{block:064x}"[-64:],
        "transaction_index": txi,
        "log_index": logi,
    }


def seed(*, block, txi, logi, supply):
    return {
        "token": TOKEN,
        "supply_raw": supply,
        "initialize_block": block,
        "initialize_transaction_index": txi,
        "initialize_log_index": logi,
    }


def test_supply_delta_rows_keep_only_mints_and_burns():
    rows = build_direct_supply_delta_rows([
        transfer(
            from_address=ZERO,
            to_address=ALICE,
            value=100,
            block=10,
            txi=1,
            logi=0,
        ),
        transfer(
            from_address=ALICE,
            to_address="0x" + "33" * 20,
            value=10,
            block=10,
            txi=2,
            logi=0,
        ),
        transfer(
            from_address=ALICE,
            to_address=ZERO,
            value=25,
            block=11,
            txi=1,
            logi=0,
        ),
    ])

    assert [row["supply_delta_raw"] for row in rows] == [100, -25]
    assert rows[0]["is_mint"] is True
    assert rows[1]["is_burn"] is True


def test_supply_timeline_derives_initialize_event_supply_from_block_end():
    deltas = build_direct_supply_delta_rows([
        transfer(
            from_address=ZERO,
            to_address=ALICE,
            value=100,
            block=10,
            txi=2,
            logi=0,
        ),
        transfer(
            from_address=ALICE,
            to_address=ZERO,
            value=50,
            block=11,
            txi=1,
            logi=0,
        ),
    ])
    timeline = DirectSupplyTimeline(
        [
            seed(block=10, txi=1, logi=0, supply=1100),
            seed(block=11, txi=2, logi=0, supply=1050),
        ],
        deltas,
    )

    assert timeline.supply_at(TOKEN, (10, 1, 0)) == 1000
    assert timeline.supply_at(TOKEN, (10, 2, 0)) == 1100
    assert timeline.supply_at(TOKEN, (11, 1, 0)) == 1050
    assert timeline.supply_at(TOKEN, (11, 2, 0)) == 1050


def test_supply_timeline_fails_when_later_pool_seed_disagrees():
    deltas = build_direct_supply_delta_rows([
        transfer(
            from_address=ALICE,
            to_address=ZERO,
            value=50,
            block=11,
            txi=1,
            logi=0,
        ),
    ])
    timeline = DirectSupplyTimeline(
        [
            seed(block=10, txi=1, logi=0, supply=1000),
            seed(block=11, txi=2, logi=0, supply=999),
        ],
        deltas,
    )

    with pytest.raises(ValueError, match="disagrees with later Initialize seed"):
        timeline.supply_at(TOKEN, (11, 2, 0))


def test_supply_timeline_rejects_target_before_first_initialize():
    timeline = DirectSupplyTimeline(
        [seed(block=10, txi=1, logi=0, supply=1000)],
        [],
    )
    with pytest.raises(ValueError, match="predates current state"):
        timeline.supply_at(TOKEN, (9, 1, 0))
