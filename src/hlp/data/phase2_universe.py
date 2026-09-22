"""Fail-closed Phase-2 eligible-universe assembly."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH, normalize_address
from hlp.data.phase2_coverage import validate_phase2_coverage_ledger


PHASE2_UNIVERSE_VERSION = "phase2-universe-v1"
PHASE2_ELIGIBILITY_THRESHOLD_USD = Decimal("100000")


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def normalize_phase2_source_eligibility_rows(
    source_id: str,
    rows: Iterable[Mapping[str, object]],
    *,
    provenance_sha256: str,
    canonical_price_series: bool,
) -> list[dict]:
    """Normalize one complete source's token summaries for universe assembly."""
    source_id = str(source_id)
    if not source_id:
        raise ValueError("Phase-2 eligibility source id is empty")
    provenance = _sha256(
        provenance_sha256,
        label=f"{source_id} eligibility provenance",
    )
    if canonical_price_series is not True:
        raise ValueError(
            f"{source_id} eligibility is not a canonical price series"
        )

    output = []
    seen: set[str] = set()
    for raw in rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(
                f"{source_id} eligibility repeats token: {token}"
            )
        seen.add(token)

        points = int(row.get("price_points", -1))
        priced = int(row.get("priced_points", -1))
        if points <= 0 or priced != points:
            raise ValueError(
                f"{source_id} eligibility has incomplete pricing: {token}"
            )
        if "unpriced_points" in row and int(
            row.get("unpriced_points", -1)
        ) != 0:
            raise ValueError(
                f"{source_id} eligibility has unpriced points: {token}"
            )
        if "pricing_complete" in row and row.get(
            "pricing_complete"
        ) is not True:
            raise ValueError(
                f"{source_id} eligibility pricing_complete changed: {token}"
            )

        raw_max = row.get("max_market_cap_proxy_usd")
        if raw_max is None:
            raise ValueError(
                f"{source_id} eligibility has no maximum market cap: {token}"
            )
        maximum = Decimal(str(raw_max))
        if maximum < 0:
            raise ValueError(
                f"{source_id} eligibility has negative maximum: {token}"
            )
        crossed = row.get("crossed_100k")
        if crossed not in {True, False}:
            raise ValueError(
                f"{source_id} eligibility crossed_100k is invalid: {token}"
            )
        expected_crossed = maximum >= PHASE2_ELIGIBILITY_THRESHOLD_USD
        if bool(crossed) != expected_crossed:
            raise ValueError(
                f"{source_id} eligibility threshold evidence disagrees: "
                f"{token}"
            )

        max_block_raw = row.get("max_market_cap_block")
        max_block = (
            None if max_block_raw is None else int(max_block_raw)
        )
        if max_block is None or max_block < 0:
            raise ValueError(
                f"{source_id} eligibility max block is invalid: {token}"
            )

        output.append({
            "source_id": source_id,
            "token": token,
            "price_points": points,
            "priced_points": priced,
            "max_market_cap_proxy_usd": str(maximum),
            "max_market_cap_block": max_block,
            "crossed_100k": bool(crossed),
            "canonical_price_series": True,
            "eligibility_provenance_sha256": provenance,
        })

    output.sort(key=lambda row: row["token"])
    return output


def build_phase2_universe(
    source_rows: Mapping[str, Iterable[Mapping[str, object]]],
    *,
    source_inventory: Iterable[Mapping[str, object]],
    coverage_ledger: Mapping[str, object],
    exclusion_rows: Iterable[Mapping[str, object]],
) -> tuple[list[dict], list[dict], dict]:
    """Assemble the address-deduplicated >=$100k universe after full coverage."""
    inventory = [dict(row) for row in source_inventory]
    coverage = validate_phase2_coverage_ledger(
        coverage_ledger,
        inventory,
    )
    if coverage["phase2_universe_coverage_complete"] is not True:
        raise ValueError(
            "Phase-2 universe requires complete coverage for every source"
        )

    inventory_ids = {
        str(row["source_id"])
        for row in inventory
    }
    supplied_ids = {str(source_id) for source_id in source_rows}
    if supplied_ids != inventory_ids:
        raise ValueError(
            "Phase-2 universe source-summary contract mismatch: "
            f"missing={sorted(inventory_ids - supplied_ids)} "
            f"extra={sorted(supplied_ids - inventory_ids)}"
        )

    exclusions: dict[str, dict] = {}
    for raw in exclusion_rows:
        row = dict(raw)
        address = normalize_address(str(row.get("address") or ""))
        if address in exclusions:
            raise ValueError(
                f"Phase-2 universe exclusion repeats address: {address}"
            )
        exclusion_class = str(row.get("exclusion_class") or "")
        identity_source = str(row.get("identity_source") or "")
        if not exclusion_class or not identity_source:
            raise ValueError(
                f"Phase-2 universe exclusion is incomplete: {address}"
            )
        exclusions[address] = {
            "exclusion_class": exclusion_class,
            "identity_source": identity_source,
        }

    for required in (ROBINHOOD_WETH, ROBINHOOD_USDG):
        address = normalize_address(required)
        if address not in exclusions:
            raise ValueError(
                f"Phase-2 universe exclusion registry lacks {address}"
            )

    by_token: dict[str, dict] = {}
    source_token_counts: dict[str, int] = {}
    for source_id in sorted(inventory_ids):
        rows = [dict(row) for row in source_rows[source_id]]
        source_token_counts[source_id] = len(rows)
        seen_source_tokens: set[str] = set()
        for row in rows:
            if str(row.get("source_id") or "") != source_id:
                raise ValueError(
                    f"Phase-2 universe source identity drift: {source_id}"
                )
            token = normalize_address(str(row.get("token") or ""))
            if token in seen_source_tokens:
                raise ValueError(
                    f"Phase-2 universe repeats {source_id} token: {token}"
                )
            seen_source_tokens.add(token)
            if row.get("canonical_price_series") is not True:
                raise ValueError(
                    f"Phase-2 universe row is not canonical: {token}"
                )
            points = int(row.get("price_points", -1))
            priced = int(row.get("priced_points", -1))
            if points <= 0 or priced != points:
                raise ValueError(
                    f"Phase-2 universe row has incomplete pricing: {token}"
                )
            provenance = _sha256(
                row.get("eligibility_provenance_sha256"),
                label=f"{source_id} eligibility row",
            )
            maximum = Decimal(
                str(row.get("max_market_cap_proxy_usd"))
            )
            if maximum < 0:
                raise ValueError(
                    f"Phase-2 universe row has negative maximum: {token}"
                )
            crossed = row.get("crossed_100k")
            if crossed not in {True, False}:
                raise ValueError(
                    f"Phase-2 universe threshold flag is invalid: {token}"
                )
            if bool(crossed) != (
                maximum >= PHASE2_ELIGIBILITY_THRESHOLD_USD
            ):
                raise ValueError(
                    f"Phase-2 universe threshold evidence disagrees: {token}"
                )
            max_block = int(row.get("max_market_cap_block", -1))
            if max_block < 0:
                raise ValueError(
                    f"Phase-2 universe max block is invalid: {token}"
                )

            current = by_token.get(token)
            if current is None:
                current = {
                    "token": token,
                    "source_ids": [],
                    "source_provenance_sha256": {},
                    "source_price_points": {},
                    "max_market_cap_proxy_usd": maximum,
                    "max_market_cap_block": max_block,
                    "crossed_100k": bool(crossed),
                }
                by_token[token] = current
            current["source_ids"].append(source_id)
            current["source_provenance_sha256"][source_id] = provenance
            current["source_price_points"][source_id] = points
            prior = Decimal(
                str(current["max_market_cap_proxy_usd"])
            )
            prior_block = int(current["max_market_cap_block"])
            if maximum > prior or (
                maximum == prior and max_block < prior_block
            ):
                current["max_market_cap_proxy_usd"] = maximum
                current["max_market_cap_block"] = max_block
            current["crossed_100k"] = (
                bool(current["crossed_100k"])
                or bool(crossed)
            )

    universe: list[dict] = []
    rejected: list[dict] = []
    overlap_tokens = 0
    excluded_eligible = 0
    below_threshold = 0
    for token, raw in by_token.items():
        source_ids = sorted(set(raw["source_ids"]))
        if len(source_ids) > 1:
            overlap_tokens += 1
        maximum = Decimal(str(raw["max_market_cap_proxy_usd"]))
        base = {
            "token": token,
            "source_ids": source_ids,
            "source_provenance_sha256": dict(sorted(
                raw["source_provenance_sha256"].items()
            )),
            "source_price_points": dict(sorted(
                raw["source_price_points"].items()
            )),
            "max_market_cap_proxy_usd": str(maximum),
            "max_market_cap_block": int(
                raw["max_market_cap_block"]
            ),
            "crossed_100k": bool(raw["crossed_100k"]),
            "eligibility_threshold_usd": "100000",
        }
        exclusion = exclusions.get(token)
        if exclusion is not None:
            if base["crossed_100k"]:
                excluded_eligible += 1
            rejected.append({
                **base,
                "universe_status": "excluded",
                **exclusion,
            })
            continue
        if not base["crossed_100k"]:
            below_threshold += 1
            rejected.append({
                **base,
                "universe_status": "below_threshold",
                "exclusion_class": None,
                "identity_source": None,
            })
            continue
        universe.append({
            **base,
            "universe_status": "eligible",
        })

    universe.sort(key=lambda row: row["token"])
    rejected.sort(key=lambda row: row["token"])
    summary = {
        "version": PHASE2_UNIVERSE_VERSION,
        "snapshot_head_block": int(
            coverage["snapshot_head_block"]
        ),
        "eligibility_threshold_usd": "100000",
        "inventory_sources": len(inventory_ids),
        "complete_source_ids": list(
            coverage["complete_source_ids"]
        ),
        "source_token_counts": dict(sorted(source_token_counts.items())),
        "observed_unique_tokens": len(by_token),
        "source_overlap_tokens": overlap_tokens,
        "eligible_tokens": len(universe),
        "rejected_tokens": len(rejected),
        "excluded_eligible_tokens": excluded_eligible,
        "below_threshold_tokens": below_threshold,
        "exclusion_addresses": len(exclusions),
        "coverage_complete": True,
        "exclusions_address_based": True,
        "canonical_price_series_required": True,
        "phase2_universe_frozen": True,
    }
    return universe, rejected, summary
