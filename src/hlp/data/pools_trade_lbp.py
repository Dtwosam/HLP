"""pools.trade Crowd Launch/LBP lifecycle summary assembly."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable


def _index_unique(rows: Iterable[dict], *, phase: str) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        token = str(row.get("token") or "").lower()
        if not token:
            raise ValueError(f"{phase} summary row has no token")
        if token in output:
            raise ValueError(
                f"duplicate pools.trade LBP {phase} summary token: {token}"
            )
        output[token] = row
    return output


def merge_pools_trade_lbp_market_cap_summaries(
    registry_rows: Iterable[dict],
    *,
    cca_summary: Iterable[dict],
    v4_summary: Iterable[dict] = (),
) -> list[dict]:
    """Merge CCA and migrated V4 evidence into one source/token summary.

    The frozen LBP registry is authoritative. Complete source reconstruction
    requires CCA summary evidence for every launch. V4 evidence is optional
    because failed/non-migrating auctions legitimately never initialize a pool.
    """
    registry: dict[str, dict] = {}
    for raw in registry_rows:
        row = dict(raw)
        token = str(row.get("token") or "").lower()
        if not token:
            raise ValueError("pools.trade LBP registry row has no token")
        if token in registry:
            raise ValueError(
                f"duplicate pools.trade LBP registry token: {token}"
            )
        registry[token] = row

    cca = _index_unique(cca_summary, phase="CCA")
    v4 = _index_unique(v4_summary, phase="V4")

    if set(cca) != set(registry):
        missing = sorted(set(registry) - set(cca))
        extra = sorted(set(cca) - set(registry))
        raise ValueError(
            "pools.trade LBP CCA summary must cover registry exactly: "
            f"missing={missing[:20]} extra={extra[:20]}"
        )
    if not set(v4).issubset(registry):
        extra = sorted(set(v4) - set(registry))
        raise ValueError(
            "pools.trade LBP V4 summary contains token outside registry: "
            f"{extra[:20]}"
        )

    output = []
    for token, launch in sorted(
        registry.items(),
        key=lambda item: (
            int(item[1]["initializer_block"]),
            item[0],
        ),
    ):
        phase_rows = [("cca", cca[token])]
        if token in v4:
            phase_rows.append(("v4", v4[token]))

        price_points = 0
        priced_points = 0
        crossed = False
        maximum: Decimal | None = None
        max_block = None
        max_phase = None
        pricing_statuses: set[str] = set()

        for phase, row in phase_rows:
            points = int(row.get("price_points", 0))
            priced = int(row.get("priced_points", 0))
            if points < 0 or priced < 0 or priced > points:
                raise ValueError(
                    f"invalid pools.trade LBP {phase} point counts: {token}"
                )
            price_points += points
            priced_points += priced
            pricing_statuses.update(
                str(status)
                for status in row.get("pricing_statuses", [])
                if str(status)
            )
            crossed = crossed or bool(row.get("crossed_100k", False))

            raw_max = row.get("max_market_cap_proxy_usd")
            if raw_max is None:
                if priced > 0:
                    raise ValueError(
                        f"priced pools.trade LBP {phase} summary has no max: "
                        f"{token}"
                    )
                continue
            value = Decimal(str(raw_max))
            if value < 0:
                raise ValueError(
                    f"negative pools.trade LBP {phase} max: {token}"
                )
            block = row.get("max_market_cap_block")
            if block is None:
                raise ValueError(
                    f"pools.trade LBP {phase} max has no block: {token}"
                )
            if maximum is None or value > maximum:
                maximum = value
                max_block = int(block)
                max_phase = phase

        unpriced_points = price_points - priced_points
        if crossed and (
            maximum is None or maximum < Decimal("100000")
        ):
            raise ValueError(
                "pools.trade LBP threshold crossing contradicts maximum: "
                f"{token}"
            )
        if (
            not crossed
            and maximum is not None
            and maximum >= Decimal("100000")
        ):
            raise ValueError(
                "pools.trade LBP maximum contradicts threshold flag: "
                f"{token}"
            )

        output.append({
            "venue": "pools.trade",
            "token": token,
            "initializer": launch["initializer"],
            "pool_id": launch["pool_id"],
            "quote_token": launch["quote_token"],
            "launch_kind": "crowd_lbp",
            "price_points": price_points,
            "priced_points": priced_points,
            "unpriced_points": unpriced_points,
            "pricing_complete": unpriced_points == 0,
            "pricing_statuses": sorted(pricing_statuses),
            "eligibility_status": (
                "eligible"
                if crossed
                else "unknown"
                if unpriced_points > 0
                else "ineligible"
            ),
            "crossed_100k": crossed,
            "max_market_cap_proxy_usd": (
                None if maximum is None else str(maximum)
            ),
            "max_market_cap_block": max_block,
            "max_market_cap_phase": max_phase,
            "has_v4_price_points": token in v4,
            "migration_block_parameter": int(
                launch["migration_block"]
            ),
        })
    return output
