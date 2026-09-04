from decimal import Decimal

from hlp.data.pons_research import (
    MIN_RECOVERY_MULTIPLE,
    annotate_pons_drawdowns_and_future_returns,
    build_pons_market_path,
    eligible_pons_tokens,
    summarize_pons_eligibility,
)


TOKEN = "0x" + "11" * 20
OTHER = "0x" + "22" * 20


def point(token, block, mcap, *, phase="v4", logi=0):
    return {
        "token": token,
        "phase": phase,
        "event_type": "swap",
        "block_number": block,
        "transaction_hash": "0x" + f"{block:064x}",
        "transaction_index": 1,
        "log_index": logi,
        "market_cap_proxy_usd": str(mcap),
    }


def test_eligibility_is_only_100k_and_keeps_pre_threshold_path():
    v2 = [
        point(TOKEN, 1, 20_000, phase="curve"),
        point(TOKEN, 2, 120_000, phase="v4"),
        point(OTHER, 3, 99_999, phase="curve"),
    ]
    path = build_pons_market_path(v2_curve_rows=v2[:1] + v2[2:], v2_v4_rows=v2[1:2])
    summary = summarize_pons_eligibility(path)
    eligible = eligible_pons_tokens(summary)
    assert eligible == {TOKEN}
    annotated = annotate_pons_drawdowns_and_future_returns(
        path, eligible_tokens=eligible
    )
    assert [row["block_number"] for row in annotated] == [1, 2]


def test_continuous_future_multiple_preserves_beyond_5x():
    path = build_pons_market_path(
        v1_rows=[
            point(TOKEN, 1, 200_000),
            point(TOKEN, 2, 50_000),
            point(TOKEN, 3, 1_000_000),
        ]
    )
    annotated = annotate_pons_drawdowns_and_future_returns(path)
    bottom = annotated[1]
    assert Decimal(bottom["drawdown_from_running_peak"]) == Decimal("0.75")
    assert Decimal(bottom["max_future_multiple"]) == Decimal("20")
    assert bottom["reached_5x_later"] is True
    assert MIN_RECOVERY_MULTIPLE == Decimal("5")
    assert annotated[-1]["max_future_multiple"] is None


def test_future_return_is_strictly_later_not_same_point():
    path = build_pons_market_path(
        v1_rows=[
            point(TOKEN, 1, 100_000),
            point(TOKEN, 2, 90_000),
        ]
    )
    annotated = annotate_pons_drawdowns_and_future_returns(path)
    assert Decimal(annotated[0]["max_future_multiple"]) == Decimal("0.9")
    assert annotated[-1]["max_future_multiple"] is None
