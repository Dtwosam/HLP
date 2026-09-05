"""Independent DEX reconciliation helpers for representative Pons samples."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable


def build_representative_pool_targets(
    sample_rows: Iterable[dict],
    registry_rows: Iterable[dict],
    registration_rows: Iterable[dict],
) -> list[dict]:
    """Map representative tokens to their frozen canonical V3/V4 pool target."""
    registry = {}
    for source in registry_rows:
        row = dict(source)
        token = row["token"].lower()
        if token in registry:
            raise ValueError(f"registry contains duplicate token {token}")
        row["token"] = token
        registry[token] = row

    registration_by_token = {}
    for source in registration_rows:
        row = dict(source)
        token = row["token"].lower()
        if token in registration_by_token:
            raise ValueError(
                f"V2 transition contains duplicate registration for {token}"
            )
        row["token"] = token
        registration_by_token[token] = row

    output = []
    seen = set()
    for source in sample_rows:
        sample = dict(source)
        token = sample["token"].lower()
        if token in seen:
            raise ValueError(
                f"representative sample contains duplicate token {token}"
            )
        seen.add(token)

        launch = registry.get(token)
        if launch is None:
            raise ValueError(
                f"representative token is absent from frozen registry: {token}"
            )
        version = sample.get("pons_version") or launch.get("version")
        if version != launch.get("version"):
            raise ValueError(
                f"representative version mismatch for {token}: "
                f"sample={version} registry={launch.get('version')}"
            )
        quote_token = launch["pair_token"].lower()

        if version == "v1":
            pool = launch.get("pool")
            if not pool:
                raise ValueError(
                    f"Pons V1 representative token has no frozen V3 pool: "
                    f"{token}"
                )
            output.append(
                {
                    "token": token,
                    "pons_version": "v1",
                    "quote_token": quote_token,
                    "pool_kind": "uniswap_v3",
                    "pool_identifier": str(pool).lower(),
                    "crosscheck_scope": "canonical_dex_pool",
                }
            )
            continue

        if version != "v2":
            raise ValueError(
                f"unsupported representative Pons version: {version}"
            )
        registration = registration_by_token.get(token)
        if registration is None:
            output.append(
                {
                    "token": token,
                    "pons_version": "v2",
                    "quote_token": quote_token,
                    "pool_kind": None,
                    "pool_identifier": None,
                    "crosscheck_scope": "no_registered_v4_pool",
                }
            )
            continue
        if registration["quote_token"].lower() != quote_token:
            raise ValueError(
                f"V2 registration quote mismatch for representative {token}"
            )
        output.append(
            {
                "token": token,
                "pons_version": "v2",
                "quote_token": quote_token,
                "pool_kind": "uniswap_v4",
                "pool_identifier": registration["pool_id"].lower(),
                "crosscheck_scope": "canonical_dex_pool",
            }
        )

    return output


def reconcile_external_pool(target: dict, external_pool: dict) -> dict:
    """Fail-closed reconciliation of one canonical pool against external data."""
    result = dict(target)
    pool_identifier = target.get("pool_identifier")
    if pool_identifier is None:
        result.update(
            {
                "external_status": "not_applicable",
                "external_match": None,
                "mismatches": [],
            }
        )
        return result

    mismatches = []
    external_identifier = str(
        external_pool.get("pool_address") or ""
    ).lower()
    if external_identifier != str(pool_identifier).lower():
        mismatches.append("pool_identifier")

    expected_tokens = {
        target["token"].lower(),
        target["quote_token"].lower(),
    }
    external_tokens = {
        str(external_pool.get("base_token") or "").lower(),
        str(external_pool.get("quote_token") or "").lower(),
    }
    if external_tokens != expected_tokens:
        mismatches.append("token_pair")

    reserve = external_pool.get("reserve_in_usd")
    if reserve is not None and Decimal(str(reserve)) < 0:
        mismatches.append("negative_reserve")

    result.update(
        {
            "external_status": (
                "matched" if not mismatches else "mismatch"
            ),
            "external_match": not mismatches,
            "mismatches": mismatches,
            "external_pool_address": external_identifier,
            "external_base_token": external_pool.get("base_token"),
            "external_quote_token": external_pool.get("quote_token"),
            "external_reserve_in_usd": reserve,
            "external_pool_created_at": external_pool.get("pool_created_at"),
        }
    )
    return result


def reconcile_price_against_ohlcv(
    *,
    canonical_price_usd: Decimal | str | int | float,
    canonical_timestamp: int,
    candles: Iterable[dict],
    candle_seconds: int,
    tolerance_bps: Decimal | str | int | float = 0,
) -> dict:
    """Check a canonical event price against the independent OHLCV envelope."""
    price = Decimal(str(canonical_price_usd))
    tolerance = Decimal(str(tolerance_bps))
    if price <= 0:
        raise ValueError("canonical price must be positive")
    if canonical_timestamp <= 0:
        raise ValueError("canonical timestamp must be positive")
    if candle_seconds <= 0:
        raise ValueError("candle_seconds must be positive")
    if tolerance < 0:
        raise ValueError("tolerance_bps cannot be negative")

    matched = None
    for source in candles:
        row = dict(source)
        start = int(row["timestamp"])
        if start <= canonical_timestamp < start + candle_seconds:
            if matched is not None:
                raise ValueError(
                    "multiple OHLCV candles contain canonical timestamp"
                )
            matched = row
    if matched is None:
        return {
            "price_match": None,
            "status": "missing_candle",
            "canonical_price_usd": str(price),
            "canonical_timestamp": canonical_timestamp,
            "tolerance_bps": str(tolerance),
        }

    low = Decimal(str(matched["low"]))
    high = Decimal(str(matched["high"]))
    if low <= 0 or high <= 0 or high < low:
        raise ValueError("invalid independent OHLCV price envelope")

    if low <= price <= high:
        outside_bps = Decimal(0)
    elif price < low:
        outside_bps = (low - price) / low * Decimal(10_000)
    else:
        outside_bps = (price - high) / high * Decimal(10_000)

    passed = outside_bps <= tolerance
    return {
        "price_match": passed,
        "status": "matched" if passed else "outside_candle",
        "canonical_price_usd": str(price),
        "canonical_timestamp": canonical_timestamp,
        "candle_timestamp": int(matched["timestamp"]),
        "candle_low_usd": str(low),
        "candle_high_usd": str(high),
        "outside_candle_bps": str(outside_bps),
        "tolerance_bps": str(tolerance),
    }
