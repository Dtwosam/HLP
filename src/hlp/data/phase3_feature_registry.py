"""Versioned Phase-3 feature definitions and leakage contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping

from hlp.data.phase3_feature_entry import PHASE3_FEATURE_SNAPSHOT_KIND


PHASE3_FEATURE_REGISTRY_VERSION = "phase3-feature-registry-v1"

FEATURE_DTYPES = frozenset({
    "decimal_string",
    "integer",
    "boolean",
    "string",
})
MISSINGNESS_POLICIES = frozenset({
    "error_if_missing",
    "null_with_flag",
    "zero_if_no_observations",
})


def build_phase3_feature_registry() -> list[dict]:
    """Return the initial causal Phase-3 feature-definition registry."""

    rows = [
        {
            "feature_id": "price.market_cap_proxy_usd_at_cutoff",
            "family": "price_drawdown",
            "dtype": "decimal_string",
            "formula": (
                "last canonical market_cap_proxy_usd at the exact "
                "first-major-dump confirmation event"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.trailing_peak_market_cap_proxy_usd",
            "family": "price_drawdown",
            "dtype": "decimal_string",
            "formula": (
                "maximum canonical market_cap_proxy_usd observed from the "
                "first token price point through the confirmation cutoff"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.drawdown_fraction_from_trailing_peak",
            "family": "price_drawdown",
            "dtype": "decimal_string",
            "formula": (
                "(trailing_peak_market_cap_proxy_usd - "
                "market_cap_proxy_usd_at_cutoff) / "
                "trailing_peak_market_cap_proxy_usd"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.max_drawdown_fraction_so_far",
            "family": "price_drawdown",
            "dtype": "decimal_string",
            "formula": (
                "maximum causal trailing-peak drawdown fraction observed "
                "through the confirmation cutoff"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.minimum_market_cap_proxy_usd_so_far",
            "family": "price_drawdown",
            "dtype": "decimal_string",
            "formula": (
                "minimum canonical market_cap_proxy_usd observed from the "
                "first token price point through the confirmation cutoff"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.expansion_multiple_from_first_observation",
            "family": "price_drawdown",
            "dtype": "decimal_string",
            "formula": (
                "market_cap_proxy_usd_at_cutoff / "
                "first_observed_market_cap_proxy_usd"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.recovery_multiple_from_minimum_so_far",
            "family": "price_drawdown",
            "dtype": "decimal_string",
            "formula": (
                "market_cap_proxy_usd_at_cutoff / "
                "minimum_market_cap_proxy_usd_so_far"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.price_points_so_far",
            "family": "price_drawdown",
            "dtype": "integer",
            "formula": (
                "count of canonical token price points at or before the "
                "confirmation cutoff"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.blocks_since_first_observation",
            "family": "price_drawdown",
            "dtype": "integer",
            "formula": (
                "confirmation cutoff block minus first canonical token "
                "price-point block"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.blocks_since_trailing_peak",
            "family": "price_drawdown",
            "dtype": "integer",
            "formula": (
                "confirmation cutoff block minus the block of the latest "
                "strict trailing market-cap peak"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "price.events_since_trailing_peak",
            "family": "price_drawdown",
            "dtype": "integer",
            "formula": (
                "canonical token price-point count after the latest strict "
                "trailing peak through the confirmation cutoff"
            ),
            "data_dependency": "phase2_research_price_path",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "trade.total_trades_so_far",
            "family": "trade_flow",
            "dtype": "integer",
            "formula": (
                "count of canonical user trade rows for the token at or "
                "before the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "zero_if_no_observations",
        },
        {
            "feature_id": "trade.buy_trades_so_far",
            "family": "trade_flow",
            "dtype": "integer",
            "formula": (
                "count of canonical buy rows for the token at or before "
                "the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "zero_if_no_observations",
        },
        {
            "feature_id": "trade.sell_trades_so_far",
            "family": "trade_flow",
            "dtype": "integer",
            "formula": (
                "count of canonical sell rows for the token at or before "
                "the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "zero_if_no_observations",
        },
        {
            "feature_id": "trade.buy_trade_share_so_far",
            "family": "trade_flow",
            "dtype": "decimal_string",
            "formula": (
                "buy_trades_so_far / total_trades_so_far"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "null_with_flag",
        },
        {
            "feature_id": "trade.unique_traders_so_far",
            "family": "trade_flow",
            "dtype": "integer",
            "formula": (
                "distinct canonical trade initiators observed for the token "
                "at or before the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "zero_if_no_observations",
        },
        {
            "feature_id": "trade.unique_buyers_so_far",
            "family": "trade_flow",
            "dtype": "integer",
            "formula": (
                "distinct canonical buy initiators observed for the token "
                "at or before the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "zero_if_no_observations",
        },
        {
            "feature_id": "trade.unique_sellers_so_far",
            "family": "trade_flow",
            "dtype": "integer",
            "formula": (
                "distinct canonical sell initiators observed for the token "
                "at or before the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "zero_if_no_observations",
        },
        {
            "feature_id": "trade.repeat_buyer_trade_share_so_far",
            "family": "trade_flow",
            "dtype": "decimal_string",
            "formula": (
                "buy trades after each buyer's first buy divided by total "
                "buy trades through the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "null_with_flag",
        },
        {
            "feature_id": "trade.repeat_seller_trade_share_so_far",
            "family": "trade_flow",
            "dtype": "decimal_string",
            "formula": (
                "sell trades after each seller's first sell divided by "
                "total sell trades through the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "null_with_flag",
        },
        {
            "feature_id": "trade.current_side_is_buy",
            "family": "trade_flow",
            "dtype": "boolean",
            "formula": (
                "true when the latest canonical user trade at or before "
                "the confirmation cutoff is a buy"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "null_with_flag",
        },
        {
            "feature_id": "trade.current_side_streak_trades",
            "family": "trade_flow",
            "dtype": "integer",
            "formula": (
                "consecutive canonical trades on the latest side ending "
                "at the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_trade_tape",
            "missingness_policy": "null_with_flag",
        },
        {
            "feature_id": "holder.holder_count",
            "family": "holder_state",
            "dtype": "integer",
            "formula": (
                "count of nonzero ERC-20 balances after replaying complete "
                "transfer history through the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_transfer_tape",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "holder.top1_balance_share",
            "family": "holder_state",
            "dtype": "decimal_string",
            "formula": (
                "largest nonzero holder balance divided by accounted token "
                "supply at the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_transfer_tape",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "holder.top5_balance_share",
            "family": "holder_state",
            "dtype": "decimal_string",
            "formula": (
                "sum of the five largest nonzero holder balances divided by "
                "accounted token supply at the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_transfer_tape",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "holder.top10_balance_share",
            "family": "holder_state",
            "dtype": "decimal_string",
            "formula": (
                "sum of the ten largest nonzero holder balances divided by "
                "accounted token supply at the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_transfer_tape",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "holder.balance_hhi",
            "family": "holder_state",
            "dtype": "decimal_string",
            "formula": (
                "sum of squared nonzero holder balance shares at the "
                "confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_transfer_tape",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "holder.balance_gini",
            "family": "holder_state",
            "dtype": "decimal_string",
            "formula": (
                "Gini coefficient of nonzero raw ERC-20 holder balances at "
                "the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_transfer_tape",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "holder.transfer_events_so_far",
            "family": "holder_state",
            "dtype": "integer",
            "formula": (
                "count of canonical ERC-20 Transfer events for the token at "
                "or before the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_transfer_tape",
            "missingness_policy": "error_if_missing",
        },
        {
            "feature_id": "holder.unique_transfer_participants_so_far",
            "family": "holder_state",
            "dtype": "integer",
            "formula": (
                "distinct nonzero from/to addresses observed in canonical "
                "ERC-20 Transfer events through the confirmation cutoff"
            ),
            "data_dependency": "phase3_canonical_transfer_tape",
            "missingness_policy": "error_if_missing",
        },
    ]
    return [
        {
            "registry_version": PHASE3_FEATURE_REGISTRY_VERSION,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "cutoff_inclusive": True,
            "future_state_allowed": False,
            "outcome_dependency_allowed": False,
            **row,
        }
        for row in rows
    ]


def validate_phase3_feature_registry(
    rows: Iterable[Mapping[str, object]],
) -> dict:
    """Validate definitions and return deterministic registry identity."""

    normalized = []
    seen = set()
    for raw in rows:
        row = dict(raw)
        if (
            str(row.get("registry_version") or "")
            != PHASE3_FEATURE_REGISTRY_VERSION
        ):
            raise ValueError("Phase-3 feature registry version changed")
        feature_id = str(row.get("feature_id") or "").strip()
        if not feature_id or feature_id in seen:
            raise ValueError(
                f"Phase-3 feature id is invalid or repeated: {feature_id!r}"
            )
        seen.add(feature_id)
        family = str(row.get("family") or "").strip()
        formula = str(row.get("formula") or "").strip()
        dependency = str(row.get("data_dependency") or "").strip()
        dtype = str(row.get("dtype") or "")
        missingness = str(row.get("missingness_policy") or "")
        if not family or not formula or not dependency:
            raise ValueError(
                f"Phase-3 feature definition is incomplete: {feature_id}"
            )
        if dtype not in FEATURE_DTYPES:
            raise ValueError(
                f"Phase-3 feature dtype is unsupported: {feature_id}"
            )
        if missingness not in MISSINGNESS_POLICIES:
            raise ValueError(
                f"Phase-3 feature missingness policy is unsupported: "
                f"{feature_id}"
            )
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError(
                f"Phase-3 feature snapshot semantics changed: {feature_id}"
            )
        if row.get("cutoff_inclusive") is not True:
            raise ValueError(
                f"Phase-3 feature cutoff semantics changed: {feature_id}"
            )
        if row.get("future_state_allowed") is not False:
            raise ValueError(
                f"Phase-3 feature allows future state: {feature_id}"
            )
        if row.get("outcome_dependency_allowed") is not False:
            raise ValueError(
                f"Phase-3 feature depends on outcomes: {feature_id}"
            )
        normalized.append({
            "registry_version": PHASE3_FEATURE_REGISTRY_VERSION,
            "feature_id": feature_id,
            "family": family,
            "dtype": dtype,
            "formula": formula,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "cutoff_inclusive": True,
            "data_dependency": dependency,
            "missingness_policy": missingness,
            "future_state_allowed": False,
            "outcome_dependency_allowed": False,
        })

    if not normalized:
        raise ValueError("Phase-3 feature registry is empty")
    normalized.sort(key=lambda row: row["feature_id"])
    payload = (
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    registry_sha = hashlib.sha256(payload).hexdigest()
    families = sorted({row["family"] for row in normalized})
    return {
        "version": PHASE3_FEATURE_REGISTRY_VERSION,
        "features": len(normalized),
        "families": families,
        "feature_ids": [row["feature_id"] for row in normalized],
        "registry_sha256": registry_sha,
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "cutoff_inclusive": True,
        "future_state_allowed": False,
        "outcome_dependency_allowed": False,
    }
