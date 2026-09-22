"""Final canonical price series for conclusive direct launches."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator, Mapping

from hlp.config import normalize_address
from hlp.data.direct_selector import (
    DIRECT_SELECTOR_FREEZE_VERSION,
    DIRECT_SELECTOR_VERSION,
    DIRECT_SOURCE_IDS,
)
from hlp.data.market_quality import rank_market_quality_snapshot


DIRECT_CANONICAL_SERIES_VERSION = "phase2-direct-canonical-series-v1"


def _market_id(row: Mapping[str, object]) -> str:
    market = str(
        row.get("market_id")
        or row.get("pool_id")
        or row.get("pool")
        or ""
    ).lower()
    if not market:
        raise ValueError("direct canonical event lacks market identity")
    return market


def _order(row: Mapping[str, object]) -> tuple[int, int, int, str]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    market = _market_id(row)
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("direct canonical event order is invalid")
    return block, tx, log, market


def _validate_selector(selector: Mapping[str, object]) -> None:
    if (
        str(selector.get("version") or "")
        != DIRECT_SELECTOR_FREEZE_VERSION
    ):
        raise ValueError("direct canonical selector freeze version changed")
    if (
        str(selector.get("selector_version") or "")
        != DIRECT_SELECTOR_VERSION
    ):
        raise ValueError("direct canonical selector version changed")
    if selector.get("selection_rule_frozen") is not True:
        raise ValueError("direct canonical selector is not frozen")
    if selector.get("source_coverage_complete") is not False:
        raise ValueError(
            "direct canonical selector unexpectedly closes source coverage"
        )
    if str(selector.get("selection_metric") or "") != (
        "active_quote_liquidity_usd"
    ):
        raise ValueError("direct canonical selector metric changed")
    if str(selector.get("tie_break_rule") or "") != (
        "stable market_id ascending"
    ):
        raise ValueError("direct canonical selector tie-break changed")
    if str(selector.get("state_semantics") or "") != (
        "latest already-observed usable market state"
    ):
        raise ValueError("direct canonical selector state semantics changed")
    if str(selector.get("canonical_volume_policy") or "") != (
        "selected market only"
    ):
        raise ValueError("direct canonical volume policy changed")
    if selector.get(
        "cross_pool_volume_double_counting_allowed"
    ) is not False:
        raise ValueError(
            "direct canonical selector permits volume double counting"
        )


def iter_frozen_direct_canonical_series(
    rows: Iterable[Mapping[str, object]],
    selector_freeze: Mapping[str, object],
    *,
    expected_tokens: Iterable[str] | None = None,
) -> Iterator[dict]:
    """Apply the frozen selector causally across all direct DEX venues.

    Before competition is observed, a token's sole market is trivially
    canonical, so its priced Initialize can enter the series without an active
    liquidity measurement. Once a second market is observed, only causal
    active-quote-liquidity states participate in ranking.

    A leadership change can be caused by the current leader losing liquidity,
    in which case the new winner's latest already-observed state is emitted at
    the triggering event time. That synthetic switch point is never volume
    eligible, preventing cross-pool volume double counting.
    """
    _validate_selector(selector_freeze)

    observed: dict[str, set[str]] = {}
    latest_quality: dict[str, dict[str, dict]] = {}
    selected: dict[str, str] = {}
    seen_events: set[tuple[str, tuple[int, int, int, str]]] = set()
    emitted_tokens: set[str] = set()
    previous_order: tuple[int, int, int, str] | None = None

    for raw in rows:
        row = dict(raw)
        source_id = str(row.get("source_id") or "")
        if source_id not in DIRECT_SOURCE_IDS:
            raise ValueError(
                f"direct canonical event has unexpected source: {source_id!r}"
            )
        token = normalize_address(str(row.get("token") or ""))
        market = _market_id(row)
        order = _order(row)
        if previous_order is not None and order < previous_order:
            raise ValueError(
                "direct canonical input is not chronological"
            )
        previous_order = order
        event_key = (token, order)
        if event_key in seen_events:
            raise ValueError(
                f"duplicate direct canonical event: {token} {order}"
            )
        seen_events.add(event_key)

        raw_mcap = row.get("market_cap_proxy_usd")
        if raw_mcap is None:
            raise ValueError(
                f"direct canonical event is unpriced: {token} {market}"
            )
        mcap = Decimal(str(raw_mcap))
        if mcap < 0:
            raise ValueError(
                f"direct canonical event has negative market cap: {market}"
            )

        state = dict(row)
        state["source_id"] = source_id
        state["token"] = token
        state["market_id"] = market
        state["market_cap_proxy_usd"] = str(mcap)

        observed.setdefault(token, set()).add(market)

        raw_depth = row.get("active_quote_liquidity_usd")
        if raw_depth is not None:
            depth = Decimal(str(raw_depth))
            if depth < 0:
                raise ValueError(
                    f"direct canonical event has negative liquidity: {market}"
                )
            state["active_quote_liquidity_usd"] = str(depth)
            latest_quality.setdefault(token, {})[market] = state

        prior_selected = selected.get(token)
        observed_markets = observed[token]

        if len(observed_markets) == 1:
            winner_id = market
            winner_state = state
            switched = (
                prior_selected is not None
                and prior_selected != winner_id
            )
            reason = "only_observed_market"
            should_emit = True
            synthetic = False
        else:
            quality_states = list(
                latest_quality.get(token, {}).values()
            )
            if not quality_states:
                continue
            ranked = rank_market_quality_snapshot(quality_states)
            winner_state = dict(ranked[0])
            winner_id = str(winner_state["market_id"]).lower()
            switched = (
                prior_selected is not None
                and prior_selected != winner_id
            )
            reason = (
                "highest_causal_active_quote_liquidity_usd"
            )
            winner_updated = (
                raw_depth is not None and market == winner_id
            )
            should_emit = winner_updated or switched
            synthetic = switched and not winner_updated

        selected[token] = winner_id
        if not should_emit:
            continue

        selected_state_order = _order(winner_state)
        item = dict(winner_state)
        item.update({
            "canonical_series_version": DIRECT_CANONICAL_SERIES_VERSION,
            "canonical_selector_version": DIRECT_SELECTOR_VERSION,
            "selection_rule_frozen": True,
            "canonical_price_series": True,
            "selected_market_id": winner_id,
            "selection_event_market_id": market,
            "leadership_switched": switched,
            "selection_reason": reason,
            "observed_markets": len(observed_markets),
            "canonical_volume_eligible": (
                not synthetic and market == winner_id
            ),
            "synthetic_selector_switch": synthetic,
            "selected_state_block_number": selected_state_order[0],
            "selected_state_transaction_index": (
                None
                if selected_state_order[1] == -1
                else selected_state_order[1]
            ),
            "selected_state_log_index": selected_state_order[2],
        })
        if synthetic:
            item["selected_state_transaction_hash"] = winner_state.get(
                "transaction_hash"
            )
            item["selected_state_event_type"] = winner_state.get(
                "event_type"
            )
            item["block_number"] = order[0]
            item["transaction_hash"] = row.get("transaction_hash")
            item["transaction_index"] = row.get("transaction_index")
            item["log_index"] = order[2]
            item["event_type"] = "selector_switch"
        emitted_tokens.add(token)
        yield item

    if expected_tokens is not None:
        expected = {
            normalize_address(str(token))
            for token in expected_tokens
        }
        actual = emitted_tokens
        if actual != expected:
            raise ValueError(
                "direct canonical token population mismatch: "
                f"missing={sorted(expected - actual)} "
                f"extra={sorted(actual - expected)}"
            )

def build_frozen_direct_canonical_series(
    rows: Iterable[Mapping[str, object]],
    selector_freeze: Mapping[str, object],
    *,
    expected_tokens: Iterable[str] | None = None,
) -> list[dict]:
    """Convenience wrapper that sorts bounded inputs before selection."""
    data = [dict(row) for row in rows]
    data.sort(key=_order)
    return list(iter_frozen_direct_canonical_series(
        data,
        selector_freeze,
        expected_tokens=expected_tokens,
    ))


def summarize_frozen_direct_canonical_series(
    rows: Iterable[Mapping[str, object]],
) -> tuple[list[dict], dict]:
    """Return universe-ready token summaries from the frozen direct series."""
    summary: dict[str, dict] = {}
    selected_markets: set[str] = set()
    switches = 0
    synthetic_switches = 0
    volume_points = 0
    points = 0

    for raw in rows:
        row = dict(raw)
        points += 1
        if row.get("selection_rule_frozen") is not True:
            raise ValueError("direct canonical row is not selector-frozen")
        if row.get("canonical_price_series") is not True:
            raise ValueError("direct canonical row is not canonical")
        if (
            str(row.get("canonical_selector_version") or "")
            != DIRECT_SELECTOR_VERSION
        ):
            raise ValueError("direct canonical row selector version changed")

        token = normalize_address(str(row.get("token") or ""))
        market = str(row.get("selected_market_id") or "").lower()
        if not market:
            raise ValueError("direct canonical row lacks selected market")
        selected_markets.add(market)
        switches += bool(row.get("leadership_switched"))
        synthetic_switches += bool(
            row.get("synthetic_selector_switch")
        )
        volume_points += bool(row.get("canonical_volume_eligible"))

        maximum = Decimal(str(row["market_cap_proxy_usd"]))
        block = int(row["block_number"])
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "price_points": 0,
                "priced_points": 0,
                "unpriced_points": 0,
                "pricing_complete": True,
                "max_market_cap_proxy_usd": maximum,
                "max_market_cap_block": block,
                "crossed_100k": False,
                "selected_market_ids": set(),
                "source_ids": set(),
                "leadership_switches": 0,
                "canonical_volume_points": 0,
                "canonical_price_series": True,
            }
            summary[token] = current
        current["price_points"] += 1
        current["priced_points"] += 1
        current["selected_market_ids"].add(market)
        current["source_ids"].add(str(row["source_id"]))
        current["leadership_switches"] += bool(
            row.get("leadership_switched")
        )
        current["canonical_volume_points"] += bool(
            row.get("canonical_volume_eligible")
        )
        prior = Decimal(str(current["max_market_cap_proxy_usd"]))
        prior_block = int(current["max_market_cap_block"])
        if maximum > prior or (
            maximum == prior and block < prior_block
        ):
            current["max_market_cap_proxy_usd"] = maximum
            current["max_market_cap_block"] = block
        if maximum >= Decimal("100000"):
            current["crossed_100k"] = True

    output = []
    for token in sorted(summary):
        current = dict(summary[token])
        current["max_market_cap_proxy_usd"] = str(
            current["max_market_cap_proxy_usd"]
        )
        current["selected_market_ids"] = sorted(
            current["selected_market_ids"]
        )
        current["source_ids"] = sorted(current["source_ids"])
        output.append(current)

    report = {
        "version": DIRECT_CANONICAL_SERIES_VERSION,
        "points": points,
        "tokens": len(output),
        "selected_markets": len(selected_markets),
        "leadership_switches": switches,
        "synthetic_selector_switches": synthetic_switches,
        "canonical_volume_points": volume_points,
        "eligible_tokens": sum(
            bool(row["crossed_100k"]) for row in output
        ),
        "canonical_selector_version": DIRECT_SELECTOR_VERSION,
        "selection_rule_frozen": True,
        "canonical_price_series": True,
        "cross_pool_volume_double_counting_allowed": False,
    }
    return output, report
