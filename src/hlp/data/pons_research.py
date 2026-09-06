"""Canonical Pons-only research paths and outcome annotations.

User-specified study constants live here and nowhere else:
- eligibility: token reached at least $100,000 market cap at any time;
- recovery floor: a later return of at least 5x.

No fixed "major dump" percentage is imposed. The full drawdown curve is
preserved so the dump structure can be learned empirically from Pons data.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from hlp.data.reconstruct import event_order


ELIGIBILITY_MARKET_CAP_USD = Decimal("100000")
MIN_RECOVERY_MULTIPLE = Decimal("5")


def _canonicalize(
    rows: Iterable[dict],
    *,
    version: str,
    default_phase: str,
    default_event_type: str,
) -> list[dict]:
    output = []
    for source in rows:
        value = source.get("market_cap_proxy_usd")
        if value is None:
            continue
        market_cap = Decimal(value)
        if market_cap <= 0:
            raise ValueError("Pons research market caps must be positive")
        row = dict(source)
        row["token"] = row["token"].lower()
        row["pons_version"] = version
        row["phase"] = row.get("phase") or default_phase
        row["event_type"] = row.get("event_type") or default_event_type
        row["market_cap_proxy_usd"] = str(market_cap)
        output.append(row)
    return output


def build_pons_market_path(
    *,
    v1_rows: Iterable[dict] = (),
    v2_curve_rows: Iterable[dict] = (),
    v2_seed_rows: Iterable[dict] = (),
    v2_v4_rows: Iterable[dict] = (),
) -> list[dict]:
    """Merge every priced Pons V1/V2 phase into one chronological path tape."""
    rows = []
    rows.extend(
        _canonicalize(
            v1_rows,
            version="v1",
            default_phase="v3",
            default_event_type="v3_swap",
        )
    )
    rows.extend(
        _canonicalize(
            v2_curve_rows,
            version="v2",
            default_phase="curve",
            default_event_type="curve_price",
        )
    )
    rows.extend(
        _canonicalize(
            v2_seed_rows,
            version="v2",
            default_phase="v4_seed",
            default_event_type="pool_graduated",
        )
    )
    rows.extend(
        _canonicalize(
            v2_v4_rows,
            version="v2",
            default_phase="v4",
            default_event_type="v4_swap",
        )
    )

    seen: set[tuple[str, int, int, int, str]] = set()
    for row in rows:
        order = event_order(row)
        key = (
            row["token"],
            order[0],
            order[1],
            order[2],
            row["phase"],
        )
        if key in seen:
            raise ValueError(f"duplicate Pons market-path point: {key}")
        seen.add(key)

    rows.sort(key=lambda row: (event_order(row), row["token"]))
    return rows


def summarize_pons_eligibility(points: Iterable[dict]) -> list[dict]:
    """Label the full Pons universe using only the $100k inclusion rule."""
    summary: dict[str, dict] = {}
    for row in points:
        token = row["token"].lower()
        mcap = Decimal(row["market_cap_proxy_usd"])
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "pons_version": row["pons_version"],
                "first_phase": row["phase"],
                "price_points": 0,
                "first_point_block": row["block_number"],
                "first_100k_block": None,
                "first_100k_phase": None,
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "max_market_cap_phase": None,
                "reached_100k": False,
            }
            summary[token] = current
        elif current["pons_version"] != row["pons_version"]:
            raise ValueError(f"Pons token appears in multiple versions: {token}")

        current["price_points"] += 1
        previous = current["max_market_cap_proxy_usd"]
        if previous is None or mcap > Decimal(previous):
            current["max_market_cap_proxy_usd"] = str(mcap)
            current["max_market_cap_block"] = row["block_number"]
            current["max_market_cap_phase"] = row["phase"]

        if (
            not current["reached_100k"]
            and mcap >= ELIGIBILITY_MARKET_CAP_USD
        ):
            current["reached_100k"] = True
            current["first_100k_block"] = row["block_number"]
            current["first_100k_phase"] = row["phase"]

    output = list(summary.values())
    output.sort(key=lambda row: (row["first_point_block"], row["token"]))
    return output


def eligible_pons_tokens(summary_rows: Iterable[dict]) -> set[str]:
    return {
        row["token"].lower()
        for row in summary_rows
        if bool(row["reached_100k"])
    }


def annotate_pons_drawdowns_and_future_returns(
    points: Iterable[dict],
    *,
    eligible_tokens: set[str] | None = None,
) -> list[dict]:
    """Attach threshold-free drawdown state and continuous future outcomes.

    Every point receives:
    - its drawdown from the running peak, with no arbitrary dump cutoff;
    - the best strictly-later market cap;
    - the exact best strictly-later multiple from that point;
    - reached_5x_later as a convenience label.

    The continuous multiple remains the primary outcome, so a 20x or 100x
    recovery is not collapsed into the same value as a 5x recovery.
    """
    allowed = (
        None
        if eligible_tokens is None
        else {token.lower() for token in eligible_tokens}
    )
    grouped: dict[str, list[dict]] = {}
    for source in points:
        token = source["token"].lower()
        if allowed is not None and token not in allowed:
            continue
        grouped.setdefault(token, []).append(dict(source))

    output: list[dict] = []
    for token, rows in grouped.items():
        rows.sort(key=event_order)
        running_peak: Decimal | None = None
        for row in rows:
            mcap = Decimal(row["market_cap_proxy_usd"])
            if running_peak is None or mcap > running_peak:
                running_peak = mcap
            row["running_peak_market_cap_usd"] = str(running_peak)
            row["drawdown_from_running_peak"] = str(
                Decimal(1) - (mcap / running_peak)
            )

        future_max: Decimal | None = None
        for row in reversed(rows):
            mcap = Decimal(row["market_cap_proxy_usd"])
            row["future_max_market_cap_usd"] = (
                None if future_max is None else str(future_max)
            )
            if future_max is None:
                row["max_future_multiple"] = None
                row["reached_5x_later"] = False
            else:
                multiple = future_max / mcap
                row["max_future_multiple"] = str(multiple)
                row["reached_5x_later"] = multiple >= MIN_RECOVERY_MULTIPLE
            if future_max is None or mcap > future_max:
                future_max = mcap

        output.extend(rows)

    output.sort(key=lambda row: (event_order(row), row["token"]))
    return output



def extract_pons_drawdown_episodes(
    annotated_points: Iterable[dict],
) -> list[dict]:
    """Partition Pons paths into threshold-free running-peak drawdown episodes.

    An episode begins at the first priced point below the current running
    peak. Its trough is the lowest point before the old peak is reclaimed.
    The episode closes when price returns to or above that peak; otherwise it
    remains open at the supplied history boundary.

    No episode is called "major" here. Depth is preserved continuously for a
    later empirical regime fit.
    """
    grouped: dict[str, list[dict]] = {}
    for source in annotated_points:
        token = source["token"].lower()
        grouped.setdefault(token, []).append(dict(source))

    episodes: list[dict] = []
    for token, rows in grouped.items():
        rows.sort(key=event_order)
        if not rows:
            continue

        peak_row = rows[0]
        peak_mcap = Decimal(peak_row["market_cap_proxy_usd"])
        active: dict | None = None
        episode_index = 0

        for row in rows[1:]:
            mcap = Decimal(row["market_cap_proxy_usd"])
            if mcap >= peak_mcap:
                if active is not None:
                    trough = active["trough_row"]
                    trough_mcap = Decimal(
                        trough["market_cap_proxy_usd"]
                    )
                    future_multiple = trough.get("max_future_multiple")
                    episodes.append(
                        {
                            "token": token,
                            "pons_version": row["pons_version"],
                            "episode_index": episode_index,
                            "peak_block": peak_row["block_number"],
                            "peak_transaction_index": peak_row.get(
                                "transaction_index"
                            ),
                            "peak_log_index": peak_row["log_index"],
                            "peak_phase": peak_row["phase"],
                            "peak_market_cap_usd": str(peak_mcap),
                            "drawdown_start_block": active[
                                "start_row"
                            ]["block_number"],
                            "trough_block": trough["block_number"],
                            "trough_transaction_index": trough.get(
                                "transaction_index"
                            ),
                            "trough_log_index": trough["log_index"],
                            "trough_phase": trough["phase"],
                            "trough_market_cap_usd": str(trough_mcap),
                            "drawdown_fraction": str(
                                Decimal(1) - trough_mcap / peak_mcap
                            ),
                            "recovered_prior_peak": True,
                            "recovery_block": row["block_number"],
                            "recovery_transaction_index": row.get(
                                "transaction_index"
                            ),
                            "recovery_log_index": row["log_index"],
                            "recovery_phase": row["phase"],
                            "recovery_market_cap_usd": str(mcap),
                            "trough_to_recovery_multiple": str(
                                mcap / trough_mcap
                            ),
                            "max_future_multiple_from_trough": (
                                future_multiple
                            ),
                            "trough_reached_5x_later": bool(
                                trough.get("reached_5x_later", False)
                            ),
                            "open_at_history_end": False,
                        }
                    )
                    episode_index += 1
                    active = None
                peak_row = row
                peak_mcap = mcap
                continue

            if active is None:
                active = {
                    "start_row": row,
                    "trough_row": row,
                }
            else:
                trough_mcap = Decimal(
                    active["trough_row"]["market_cap_proxy_usd"]
                )
                if mcap < trough_mcap:
                    active["trough_row"] = row

        if active is not None:
            trough = active["trough_row"]
            trough_mcap = Decimal(trough["market_cap_proxy_usd"])
            future_multiple = trough.get("max_future_multiple")
            episodes.append(
                {
                    "token": token,
                    "pons_version": trough["pons_version"],
                    "episode_index": episode_index,
                    "peak_block": peak_row["block_number"],
                    "peak_transaction_index": peak_row.get(
                        "transaction_index"
                    ),
                    "peak_log_index": peak_row["log_index"],
                    "peak_phase": peak_row["phase"],
                    "peak_market_cap_usd": str(peak_mcap),
                    "drawdown_start_block": active["start_row"][
                        "block_number"
                    ],
                    "trough_block": trough["block_number"],
                    "trough_transaction_index": trough.get(
                        "transaction_index"
                    ),
                    "trough_log_index": trough["log_index"],
                    "trough_phase": trough["phase"],
                    "trough_market_cap_usd": str(trough_mcap),
                    "drawdown_fraction": str(
                        Decimal(1) - trough_mcap / peak_mcap
                    ),
                    "recovered_prior_peak": False,
                    "recovery_block": None,
                    "recovery_transaction_index": None,
                    "recovery_log_index": None,
                    "recovery_phase": None,
                    "recovery_market_cap_usd": None,
                    "trough_to_recovery_multiple": None,
                    "max_future_multiple_from_trough": future_multiple,
                    "trough_reached_5x_later": bool(
                        trough.get("reached_5x_later", False)
                    ),
                    "open_at_history_end": True,
                }
            )

    episodes.sort(
        key=lambda row: (
            row["peak_block"],
            -1
            if row["peak_transaction_index"] is None
            else row["peak_transaction_index"],
            row["peak_log_index"],
            row["token"],
            row["episode_index"],
        )
    )
    return episodes
