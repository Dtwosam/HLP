from decimal import Decimal

import pytest

from hlp.data.pons_representative_prices import (
    summarize_representative_priced_paths,
    validate_representative_priced_path_rows,
)


def _token(index: int) -> str:
    return "0x" + f"{index:040x}"


def _sample():
    return [
        {
            "token": _token(index),
            "pons_version": "v1" if index <= 5 else "v2",
            "sample_group": "runner" if index % 2 else "failure",
            "launch_block": 1000 + index,
        }
        for index in range(1, 11)
    ]


def _rows():
    rows = []
    for index, sample in enumerate(_sample(), start=1):
        phase = "v1_v3" if sample["pons_version"] == "v1" else "v2_curve"
        for offset, market_cap in [(1, 100_000 + index), (2, 200_000 + index)]:
            rows.append(
                {
                    "token": sample["token"],
                    "pons_version": sample["pons_version"],
                    "price_path_phase": phase,
                    "block_number": sample["launch_block"] + offset,
                    "transaction_index": offset,
                    "log_index": 0,
                    "pricing_status": "priced_weth_usdg",
                    "quote_per_token": "1.5",
                    "token_price_usd": str(Decimal(market_cap) / Decimal(1_000_000)),
                    "market_cap_proxy_usd": str(market_cap),
                }
            )
    rows.sort(
        key=lambda row: (
            row["block_number"],
            row["transaction_index"],
            row["log_index"],
            row["price_path_phase"],
            row["token"],
        )
    )
    return rows


def test_representative_priced_path_validates_and_summarizes_exact_cohort():
    sample = _sample()
    rows = validate_representative_priced_path_rows(_rows(), sample)
    summary = summarize_representative_priced_paths(rows, sample)

    assert len(rows) == 20
    assert len(summary) == 10
    assert all(row["price_points"] == 2 for row in summary)
    assert all(row["priced_points"] == 2 for row in summary)
    assert all(row["unpriced_points"] == 0 for row in summary)
    assert all(row["pricing_complete"] is True for row in summary)
    first = next(row for row in summary if row["token"] == _token(1))
    assert first["phase_counts"] == {"v1_v3": 2}
    assert Decimal(first["max_market_cap_proxy_usd"]) == Decimal("200001")
    assert first["max_market_cap_block"] == 1003
    v2 = next(row for row in summary if row["token"] == _token(6))
    assert v2["phase_counts"] == {"v2_curve": 2}


def test_representative_priced_path_allows_explicit_unpriced_interval():
    sample = _sample()
    rows = _rows()
    target = next(row for row in rows if row["token"] == _token(1))
    target["market_cap_proxy_usd"] = None
    target["token_price_usd"] = None
    target["quote_per_token"] = None
    target["pricing_status"] = "unsupported_quote"

    validated = validate_representative_priced_path_rows(rows, sample)
    summary = summarize_representative_priced_paths(validated, sample)
    first = next(row for row in summary if row["token"] == _token(1))
    assert first["price_points"] == 2
    assert first["priced_points"] == 1
    assert first["unpriced_points"] == 1
    assert first["pricing_complete"] is False


def test_representative_priced_path_rejects_wrong_phase_for_version():
    sample = _sample()
    rows = _rows()
    rows[0]["price_path_phase"] = "v2_curve"

    with pytest.raises(ValueError, match="non-V3 price phase"):
        validate_representative_priced_path_rows(rows, sample)


def test_representative_priced_path_rejects_missing_token_coverage():
    sample = _sample()
    rows = [
        row for row in _rows()
        if row["token"] != _token(10)
    ]

    with pytest.raises(ValueError, match="coverage missing"):
        validate_representative_priced_path_rows(rows, sample)


def test_representative_priced_path_rejects_non_chronological_rows():
    sample = _sample()
    rows = _rows()
    rows[0], rows[-1] = rows[-1], rows[0]

    with pytest.raises(ValueError, match="not chronological"):
        validate_representative_priced_path_rows(rows, sample)


def test_representative_priced_path_rejects_unpriced_row_with_usd_price():
    sample = _sample()
    rows = _rows()
    rows[0]["market_cap_proxy_usd"] = None

    with pytest.raises(ValueError, match="has token USD price"):
        validate_representative_priced_path_rows(rows, sample)
