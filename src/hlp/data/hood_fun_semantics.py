"""Fail-closed hood.fun reserve-transition semantic audits."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

from hlp.data.types import HoodFunEvent


HOOD_FUN_CURVE_SEMANTICS_VERSION = "hood-fun-curve-semantics-v1"


def _order(row: HoodFunEvent) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def audit_hood_fun_curve_semantics(
    events: Iterable[HoodFunEvent],
    launch_registry: Iterable[Mapping[str, object]],
) -> dict:
    """Prove decoded virtual reserves evolve consistently after each trade.

    This audit intentionally does not infer price from trade amounts. It checks
    that the decoded post-trade virtual reserves are causally consistent with
    the prior decoded state and the emitted token/quote/fee amounts. Supply is
    checked separately against ERC-20 state by the evidence workflow.
    """
    event_rows = sorted(list(events), key=_order)
    registry: dict[str, dict] = {}
    for raw in launch_registry:
        token = str(raw.get("token") or "").lower()
        if not token:
            raise ValueError("hood.fun registry contains empty token")
        if token in registry:
            raise ValueError(f"duplicate hood.fun registry token: {token}")
        quote = int(raw.get("initial_virtual_quote_raw", 0))
        token_reserve = int(raw.get("initial_virtual_token_raw", 0))
        if quote <= 0 or token_reserve <= 0:
            raise ValueError(
                f"hood.fun registry has invalid initial reserves: {token}"
            )
        registry[token] = {
            "order": (
                int(raw.get("launch_block", -1)),
                int(
                    -1
                    if raw.get("launch_transaction_index") is None
                    else raw["launch_transaction_index"]
                ),
                int(raw.get("launch_log_index", -1)),
            ),
            "quote": quote,
            "token": token_reserve,
        }

    if not registry:
        raise ValueError("hood.fun semantic audit has no launch registry")

    created: dict[str, HoodFunEvent] = {}
    for event in event_rows:
        if event.event_type != "token_created":
            continue
        token = event.token.lower()
        if token not in registry:
            continue
        if token in created:
            raise ValueError(
                f"duplicate hood.fun TokenCreated in semantic audit: {token}"
            )
        created[token] = event

    if set(created) != set(registry):
        missing = sorted(set(registry) - set(created))
        raise ValueError(
            "hood.fun semantic audit registry lacks matching TokenCreated: "
            f"{missing[:10]}"
        )
    for token, event in created.items():
        launch = registry[token]
        if _order(event) != launch["order"]:
            raise ValueError(
                f"hood.fun launch order drift in semantic audit: {token}"
            )
        if (
            event.virtual_quote_raw != launch["quote"]
            or event.virtual_token_raw != launch["token"]
        ):
            raise ValueError(
                f"hood.fun launch reserve drift in semantic audit: {token}"
            )

    state = {
        token: {
            "quote": row["quote"],
            "token": row["token"],
        }
        for token, row in registry.items()
    }
    formulas: Counter[str] = Counter()
    checked_tokens: set[str] = set()
    checked = 0
    orphan_trades = 0

    for event in event_rows:
        if event.event_type != "trade":
            continue
        token = event.token.lower()
        launch = registry.get(token)
        if launch is None:
            orphan_trades += 1
            continue
        if _order(event) <= launch["order"]:
            raise ValueError(
                f"hood.fun trade is not after launch: {token}"
            )
        if (
            event.is_buy is None
            or event.quote_amount_raw is None
            or event.token_amount_raw is None
            or event.fee_raw is None
            or event.virtual_quote_raw is None
            or event.virtual_token_raw is None
        ):
            raise ValueError(
                f"hood.fun trade is missing reserve fields: {token}"
            )
        if (
            event.quote_amount_raw < 0
            or event.token_amount_raw < 0
            or event.fee_raw < 0
            or event.virtual_quote_raw <= 0
            or event.virtual_token_raw <= 0
        ):
            raise ValueError(
                f"hood.fun trade has invalid reserve amounts: {token}"
            )

        current = state[token]
        prev_q = int(current["quote"])
        prev_t = int(current["token"])
        if event.is_buy:
            expected_token = prev_t - event.token_amount_raw
            candidates = {
                "buy_plus_net": (
                    prev_q + event.quote_amount_raw - event.fee_raw
                ),
                "buy_plus_gross": prev_q + event.quote_amount_raw,
            }
        else:
            expected_token = prev_t + event.token_amount_raw
            candidates = {
                "sell_minus_gross": prev_q - event.quote_amount_raw,
                "sell_minus_net": (
                    prev_q - event.quote_amount_raw - event.fee_raw
                ),
                "sell_minus_gross_plus_fee": (
                    prev_q - event.quote_amount_raw + event.fee_raw
                ),
            }

        if expected_token != event.virtual_token_raw:
            raise ValueError(
                f"hood.fun token reserve conservation failed: {token}"
            )
        matches = sorted(
            name
            for name, value in candidates.items()
            if value == event.virtual_quote_raw
        )
        if not matches:
            raise ValueError(
                f"hood.fun quote reserve conservation failed: {token}"
            )

        formula = "|".join(matches)
        formulas[formula] += 1
        checked_tokens.add(token)
        checked += 1
        current["quote"] = event.virtual_quote_raw
        current["token"] = event.virtual_token_raw

    if checked <= 0:
        raise ValueError(
            "hood.fun semantic audit has no sequential launch-linked trades"
        )

    return {
        "version": HOOD_FUN_CURVE_SEMANTICS_VERSION,
        "registry_tokens": len(registry),
        "launches_checked": len(created),
        "checked_sequential_trades": checked,
        "tokens_with_checked_trades": len(checked_tokens),
        "orphan_trades_ignored": orphan_trades,
        "reserve_formula_counts": dict(sorted(formulas.items())),
        "reserve_conservation_complete": True,
    }
