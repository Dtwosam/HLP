"""Evidence-only trench.today LimitReach to DEX market attribution."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from hlp.config import ROBINHOOD_WETH, normalize_address
from hlp.data.direct_quotes import ZERO_ADDRESS


def _order(
    block: object,
    transaction_index: object,
    log_index: object,
) -> tuple[int, int, int]:
    return (
        int(block),
        -1 if transaction_index is None else int(transaction_index),
        int(log_index),
    )


def _dex_quote(address: str) -> str:
    quote = normalize_address(address)
    if quote == normalize_address(ZERO_ADDRESS):
        return normalize_address(ROBINHOOD_WETH)
    return quote


def build_trench_limit_market_candidates(
    trench_registry: Iterable[Mapping[str, object]],
    market_registries: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Join every LimitReach token to all exact token/quote DEX candidates.

    LimitReach does not identify a destination market. This function therefore
    preserves every address-compatible V3/V4 candidate and records only
    observable timing relationships. It deliberately does not select a market.
    """
    markets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    seen_markets: set[tuple[str, str]] = set()
    for raw in market_registries:
        row = dict(raw)
        if str(row.get("source_kind") or "") != "direct_dex":
            raise ValueError("trench handoff candidate is not direct_dex")
        source_id = str(row.get("source_id") or "")
        venue = str(row.get("venue") or "")
        if not source_id or not venue:
            raise ValueError("trench handoff candidate lacks source identity")
        token = normalize_address(str(row["token"]))
        quote = normalize_address(str(row["quote_token"]))
        market_kind = "v4_pool_id" if row.get("pool_id") else "v3_pool"
        market_id = str(row.get("pool_id") or row.get("pool") or "").lower()
        if not market_id:
            raise ValueError("trench handoff candidate lacks market identity")
        identity = (source_id, market_id)
        if identity in seen_markets:
            raise ValueError(
                f"duplicate trench handoff market: {source_id} {market_id}"
            )
        seen_markets.add(identity)
        initialize_order = _order(
            row["initialize_block"],
            row.get("initialize_transaction_index"),
            row["initialize_log_index"],
        )
        markets[(token, quote)].append({
            "market_source_id": source_id,
            "market_venue": venue,
            "market_kind": market_kind,
            "market_id": market_id,
            "market_quote_token": quote,
            "market_initialize_block": initialize_order[0],
            "market_initialize_transaction_hash": str(
                row.get("initialize_transaction_hash") or ""
            ).lower(),
            "market_initialize_transaction_index": (
                None if initialize_order[1] < 0 else initialize_order[1]
            ),
            "market_initialize_log_index": initialize_order[2],
            "market_initialize_order": initialize_order,
        })

    output: list[dict] = []
    seen_tokens: set[str] = set()
    for raw in trench_registry:
        row = dict(raw)
        if row.get("limit_reach_block") is None:
            continue
        token = normalize_address(str(row["token"]))
        if token in seen_tokens:
            raise ValueError(f"duplicate trench LimitReach token: {token}")
        seen_tokens.add(token)

        curve_quote = normalize_address(str(row["quote_token"]))
        dex_quote = _dex_quote(curve_quote)
        limit_order = _order(
            row["limit_reach_block"],
            row.get("limit_reach_transaction_index"),
            row["limit_reach_log_index"],
        )
        limit_tx = str(
            row.get("limit_reach_transaction_hash") or ""
        ).lower()
        candidates = sorted(
            markets.get((token, dex_quote), []),
            key=lambda item: (
                item["market_initialize_order"],
                item["market_source_id"],
                item["market_id"],
            ),
        )
        base = {
            "source_id": "trench_today",
            "token": token,
            "curve_quote_token": curve_quote,
            "dex_quote_token": dex_quote,
            "limit_reach_block": limit_order[0],
            "limit_reach_transaction_hash": limit_tx,
            "limit_reach_transaction_index": (
                None if limit_order[1] < 0 else limit_order[1]
            ),
            "limit_reach_log_index": limit_order[2],
            "candidate_count_for_token": len(candidates),
            "handoff_rule_frozen": False,
            "source_coverage_complete": False,
        }
        if not candidates:
            output.append({
                **base,
                "candidate_status": "no_matching_direct_market",
                "market_source_id": None,
                "market_venue": None,
                "market_kind": None,
                "market_id": None,
                "market_quote_token": None,
                "market_initialize_block": None,
                "market_initialize_transaction_hash": None,
                "market_initialize_transaction_index": None,
                "market_initialize_log_index": None,
                "initialize_block_delta": None,
                "initialize_order_relation": None,
                "same_block": False,
                "same_transaction": False,
            })
            continue

        for market in candidates:
            initialize_order = market["market_initialize_order"]
            if initialize_order < limit_order:
                relation = "before_limit"
            elif initialize_order == limit_order:
                relation = "same_order"
            else:
                relation = "after_limit"
            init_tx = market["market_initialize_transaction_hash"]
            output.append({
                **base,
                "candidate_status": "matching_direct_market",
                "market_source_id": market["market_source_id"],
                "market_venue": market["market_venue"],
                "market_kind": market["market_kind"],
                "market_id": market["market_id"],
                "market_quote_token": market["market_quote_token"],
                "market_initialize_block": initialize_order[0],
                "market_initialize_transaction_hash": init_tx,
                "market_initialize_transaction_index": market[
                    "market_initialize_transaction_index"
                ],
                "market_initialize_log_index": initialize_order[2],
                "initialize_block_delta": (
                    initialize_order[0] - limit_order[0]
                ),
                "initialize_order_relation": relation,
                "same_block": initialize_order[0] == limit_order[0],
                "same_transaction": bool(
                    limit_tx and init_tx and limit_tx == init_tx
                ),
            })

    output.sort(
        key=lambda row: (
            row["limit_reach_block"],
            row["token"],
            "" if row["market_source_id"] is None else row["market_source_id"],
            "" if row["market_id"] is None else row["market_id"],
        )
    )
    return output


def summarize_trench_limit_market_candidates(
    rows: Iterable[Mapping[str, object]],
) -> dict:
    data = [dict(row) for row in rows]
    by_token: dict[str, list[dict]] = defaultdict(list)
    for row in data:
        by_token[normalize_address(str(row["token"]))].append(row)

    matched_tokens = {
        token
        for token, token_rows in by_token.items()
        if any(
            row.get("candidate_status") == "matching_direct_market"
            for row in token_rows
        )
    }
    unmatched_tokens = sorted(set(by_token) - matched_tokens)
    candidate_counts = {
        token: max(
            int(row.get("candidate_count_for_token", 0))
            for row in token_rows
        )
        for token, token_rows in by_token.items()
    }
    matched_rows = [
        row
        for row in data
        if row.get("candidate_status") == "matching_direct_market"
    ]
    same_tx_tokens = {
        normalize_address(str(row["token"]))
        for row in matched_rows
        if row.get("same_transaction") is True
    }
    same_block_tokens = {
        normalize_address(str(row["token"]))
        for row in matched_rows
        if row.get("same_block") is True
    }

    return {
        "limit_reach_tokens": len(by_token),
        "candidate_rows": len(matched_rows),
        "tokens_with_candidates": len(matched_tokens),
        "tokens_without_candidates": len(unmatched_tokens),
        "unmatched_tokens": unmatched_tokens,
        "single_candidate_tokens": sum(
            count == 1 for count in candidate_counts.values()
        ),
        "multi_candidate_tokens": sum(
            count > 1 for count in candidate_counts.values()
        ),
        "same_transaction_tokens": len(same_tx_tokens),
        "same_block_tokens": len(same_block_tokens),
        "candidate_source_ids": sorted({
            str(row["market_source_id"])
            for row in matched_rows
        }),
        "candidate_venues": sorted({
            str(row["market_venue"])
            for row in matched_rows
        }),
        "handoff_rule_frozen": False,
        "source_coverage_complete": False,
    }


TRENCH_HANDOFF_RULE_VERSION = "trench-limit-same-transaction-after-v1"


def freeze_trench_limit_market_handoffs(
    rows: Iterable[Mapping[str, object]],
) -> tuple[list[dict], dict]:
    """Freeze only an unambiguous same-transaction post-LimitReach handoff.

    The rule is intentionally strict and empirical. Every LimitReach token must
    have exactly one matching direct market initialized later in the exact same
    transaction. Pre-existing or later unrelated markets may remain in the
    evidence set, but they cannot be selected. Missing or multiple qualifying
    markets fail closed instead of guessing.
    """
    data = [dict(row) for row in rows]
    if not data:
        raise ValueError("trench handoff freeze has no candidate evidence")

    by_token: dict[str, list[dict]] = defaultdict(list)
    for row in data:
        if str(row.get("source_id") or "") != "trench_today":
            raise ValueError("trench handoff evidence source changed")
        if row.get("handoff_rule_frozen") is not False:
            raise ValueError(
                "trench handoff evidence must remain unfrozen before decision"
            )
        if row.get("source_coverage_complete") is not False:
            raise ValueError(
                "trench handoff evidence cannot claim source coverage"
            )
        token = normalize_address(str(row["token"]))
        by_token[token].append(row)

    selected: list[dict] = []
    for token, token_rows in sorted(by_token.items()):
        declared_counts = {
            int(row.get("candidate_count_for_token", -1))
            for row in token_rows
        }
        if len(declared_counts) != 1 or min(declared_counts) < 0:
            raise ValueError(
                f"trench candidate count drift for token: {token}"
            )

        qualifying = []
        for row in token_rows:
            if row.get("candidate_status") != "matching_direct_market":
                continue
            if row.get("same_transaction") is not True:
                continue
            if row.get("same_block") is not True:
                raise ValueError(
                    f"trench same-transaction candidate not same-block: {token}"
                )
            if row.get("initialize_order_relation") != "after_limit":
                continue

            limit_order = _order(
                row["limit_reach_block"],
                row.get("limit_reach_transaction_index"),
                row["limit_reach_log_index"],
            )
            initialize_order = _order(
                row["market_initialize_block"],
                row.get("market_initialize_transaction_index"),
                row["market_initialize_log_index"],
            )
            limit_tx = str(
                row.get("limit_reach_transaction_hash") or ""
            ).lower()
            init_tx = str(
                row.get("market_initialize_transaction_hash") or ""
            ).lower()
            if not limit_tx or init_tx != limit_tx:
                raise ValueError(
                    f"trench same-transaction hash drift: {token}"
                )
            if initialize_order <= limit_order:
                raise ValueError(
                    f"trench handoff Initialize is not after LimitReach: {token}"
                )
            qualifying.append(row)

        if len(qualifying) != 1:
            raise ValueError(
                "trench handoff is not uniquely same-transaction after "
                f"LimitReach: {token} candidates={len(qualifying)}"
            )

        row = qualifying[0]
        selected.append({
            "source_id": "trench_today",
            "token": token,
            "curve_quote_token": normalize_address(
                str(row["curve_quote_token"])
            ),
            "dex_quote_token": normalize_address(
                str(row["dex_quote_token"])
            ),
            "limit_reach_block": int(row["limit_reach_block"]),
            "limit_reach_transaction_hash": str(
                row["limit_reach_transaction_hash"]
            ).lower(),
            "limit_reach_transaction_index": row.get(
                "limit_reach_transaction_index"
            ),
            "limit_reach_log_index": int(row["limit_reach_log_index"]),
            "market_source_id": str(row["market_source_id"]),
            "market_venue": str(row["market_venue"]),
            "market_kind": str(row["market_kind"]),
            "market_id": str(row["market_id"]).lower(),
            "market_quote_token": normalize_address(
                str(row["market_quote_token"])
            ),
            "market_initialize_block": int(
                row["market_initialize_block"]
            ),
            "market_initialize_transaction_hash": str(
                row["market_initialize_transaction_hash"]
            ).lower(),
            "market_initialize_transaction_index": row.get(
                "market_initialize_transaction_index"
            ),
            "market_initialize_log_index": int(
                row["market_initialize_log_index"]
            ),
            "handoff_rule_version": TRENCH_HANDOFF_RULE_VERSION,
            "handoff_rule_frozen": True,
            "selection_reason": (
                "unique direct market initialized after LimitReach "
                "in the exact same transaction"
            ),
            "source_coverage_complete": False,
        })

    summary = {
        "handoff_rule_version": TRENCH_HANDOFF_RULE_VERSION,
        "handoff_rule_frozen": True,
        "limit_reach_tokens": len(by_token),
        "selected_handoffs": len(selected),
        "candidate_rows_examined": len(data),
        "selected_market_source_ids": sorted({
            row["market_source_id"] for row in selected
        }),
        "selected_market_venues": sorted({
            row["market_venue"] for row in selected
        }),
        "all_limit_reach_tokens_resolved": (
            len(selected) == len(by_token)
        ),
        "source_coverage_complete": False,
    }
    if not summary["all_limit_reach_tokens_resolved"]:
        raise ValueError("trench handoff freeze left unresolved tokens")
    return selected, summary

