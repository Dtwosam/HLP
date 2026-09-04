from decimal import Decimal

from hlp.data.transition import summarize_v2_transition_continuity


TOKEN = "0x" + "11" * 20


def row(block, tx, price, phase):
    return {
        "token": TOKEN,
        "block_number": block,
        "transaction_index": tx,
        "log_index": 0,
        "quote_per_token": str(price),
        "phase": phase,
    }


def test_transition_continuity_uses_last_curve_and_first_v4():
    result = summarize_v2_transition_continuity(
        [row(10, 1, Decimal("1.00"), "curve"), row(11, 1, Decimal("1.02"), "curve")],
        [row(12, 1, Decimal("1.021"), "v4_seed")],
        [row(12, 3, Decimal("1.025"), "v4"), row(13, 1, Decimal("1.03"), "v4")],
    )
    assert len(result) == 1
    assert result[0]["last_curve_block"] == 11
    assert result[0]["first_v4_swap_block"] == 12
    assert Decimal(result[0]["curve_to_seed_bps"]) > 0
    assert Decimal(result[0]["seed_to_first_v4_bps"]) > 0


def test_transition_tracks_initialize_before_graduation_event():
    init = row(12, 1, Decimal("1.020"), "v4")
    init["event_type"] = "v4_initialize"
    seed = row(12, 2, Decimal("1.021"), "v4_seed")
    swap = row(12, 3, Decimal("1.025"), "v4")
    swap["event_type"] = "v4_swap"

    result = summarize_v2_transition_continuity(
        [row(11, 1, Decimal("1.00"), "curve")],
        [seed],
        [init, swap],
    )[0]

    assert result["first_v4_initialize_block"] == 12
    assert result["first_v4_swap_block"] == 12
    assert Decimal(result["curve_to_v4_initialize_bps"]) > 0
    assert Decimal(result["v4_initialize_to_seed_bps"]) > 0
    assert Decimal(result["seed_to_first_v4_bps"]) > 0
