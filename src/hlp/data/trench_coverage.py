"""Fail-closed trench.today Phase-2 curve coverage validation."""

from __future__ import annotations

from typing import Mapping


TRENCH_CURVE_COVERAGE_VERSION = "phase2-trench-curve-coverage-v1"


def _nonnegative(value: object, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if result < 0:
        raise ValueError(f"{field} cannot be negative")
    return result


def _sha256(value: object, *, field: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64:
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be a SHA-256 hex digest") from exc
    return text


def validate_trench_curve_coverage_report(
    report: Mapping[str, object],
    *,
    required_start_block: int,
    snapshot_head_block: int,
) -> dict:
    """Validate complete curve reconstruction without closing source coverage."""
    if str(report.get("version") or "") != TRENCH_CURVE_COVERAGE_VERSION:
        raise ValueError("trench.today curve coverage version changed")
    if str(report.get("source_id") or "") != "trench_today":
        raise ValueError("trench.today curve coverage source changed")
    if str(report.get("coverage_segment") or "") != "bonding_curve":
        raise ValueError("trench.today curve coverage segment changed")
    if report.get("source_coverage_complete") is not False:
        raise ValueError(
            "trench.today curve segment cannot close source coverage"
        )

    required = _nonnegative(
        report.get("required_start_block"),
        field="required_start_block",
    )
    snapshot = _nonnegative(
        report.get("snapshot_head_block"),
        field="snapshot_head_block",
    )
    if required != int(required_start_block):
        raise ValueError("trench.today curve required start changed")
    if snapshot != int(snapshot_head_block):
        raise ValueError("trench.today curve snapshot changed")
    if report.get("continuous_event_scan") is not True:
        raise ValueError("trench.today curve event scan is not continuous")
    missing = report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError("trench.today curve coverage has missing ranges")

    tokens = _nonnegative(
        report.get("tokens_discovered"),
        field="tokens_discovered",
    )
    sync_tokens = _nonnegative(
        report.get("tokens_with_syncs"),
        field="tokens_with_syncs",
    )
    limited = _nonnegative(
        report.get("limit_reach_tokens"),
        field="limit_reach_tokens",
    )
    points = _nonnegative(
        report.get("curve_price_points"),
        field="curve_price_points",
    )
    priced = _nonnegative(
        report.get("curve_priced_points"),
        field="curve_priced_points",
    )
    crossed = _nonnegative(
        report.get("curve_tokens_crossed_100k"),
        field="curve_tokens_crossed_100k",
    )
    if sync_tokens > tokens:
        raise ValueError(
            "trench.today Sync-token count exceeds launch population"
        )
    if limited > tokens:
        raise ValueError(
            "trench.today LimitReach count exceeds launch population"
        )
    if priced != points:
        raise ValueError("trench.today curve coverage has unpriced points")
    if crossed > sync_tokens:
        raise ValueError(
            "trench.today curve eligibility exceeds Sync-token population"
        )

    hashes = {}
    for field in (
        "event_tape_sha256",
        "registry_sha256",
        "quote_decimals_sha256",
        "quote_feed_specs_sha256",
        "curve_points_sha256",
        "curve_summary_sha256",
    ):
        hashes[field] = _sha256(report.get(field), field=field)

    blocking = report.get("blocking_reason")
    if limited:
        if str(blocking or "") != "post_limit_dex_lifecycle_unresolved":
            raise ValueError(
                "trench.today LimitReach coverage lacks DEX-lifecycle blocker"
            )
    elif blocking is not None:
        raise ValueError(
            "trench.today curve coverage has unexpected blocking_reason"
        )

    return {
        "version": TRENCH_CURVE_COVERAGE_VERSION,
        "source_id": "trench_today",
        "coverage_segment": "bonding_curve",
        "required_start_block": required,
        "snapshot_head_block": snapshot,
        "continuous_event_scan": True,
        "missing_ranges": [],
        "tokens_discovered": tokens,
        "tokens_with_syncs": sync_tokens,
        "limit_reach_tokens": limited,
        "curve_price_points": points,
        "curve_priced_points": priced,
        "curve_tokens_crossed_100k": crossed,
        **hashes,
        "blocking_reason": (
            None if blocking is None else str(blocking)
        ),
        "source_coverage_complete": False,
    }


TRENCH_SOURCE_COVERAGE_VERSION = "phase2-trench-source-coverage-v1"


def _order(row: Mapping[str, object]) -> tuple[int, int, int]:
    return (
        int(row["block_number"]),
        -1
        if row.get("transaction_index") is None
        else int(row["transaction_index"]),
        int(row["log_index"]),
    )


def summarize_trench_post_limit_market_caps(
    rows,
    handoffs,
) -> list[dict]:
    """Summarize fully priced selected-market history after LimitReach."""
    by_token: dict[str, dict] = {}
    for raw in handoffs:
        row = dict(raw)
        token = str(row["token"]).lower()
        if token in by_token:
            raise ValueError(f"duplicate trench handoff token: {token}")
        if row.get("handoff_rule_frozen") is not True:
            raise ValueError(f"trench handoff is not frozen: {token}")
        market_id = str(row.get("market_id") or "").lower()
        if not market_id:
            raise ValueError(f"trench handoff lacks market id: {token}")
        by_token[token] = {
            "market_id": market_id,
            "market_source_id": str(row["market_source_id"]),
            "market_venue": str(row["market_venue"]),
            "lifecycle_order": (
                int(row["limit_reach_block"]),
                -1
                if row.get("limit_reach_transaction_index") is None
                else int(row["limit_reach_transaction_index"]),
                int(row["limit_reach_log_index"]),
            ),
        }

    summary: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        if str(row.get("source_id") or "") != "trench_today":
            raise ValueError("trench post-limit point source changed")
        token = str(row["token"]).lower()
        handoff = by_token.get(token)
        if handoff is None:
            raise ValueError(
                f"trench post-limit point has no frozen handoff: {token}"
            )
        market_id = str(row.get("market_id") or "").lower()
        if market_id != handoff["market_id"]:
            raise ValueError(
                f"trench post-limit market identity drift: {token}"
            )
        order = _order(row)
        if order <= handoff["lifecycle_order"]:
            raise ValueError(
                f"trench post-limit point does not follow LimitReach: {token}"
            )
        value = row.get("market_cap_proxy_usd")
        if value is None:
            raise ValueError(
                f"trench post-limit point is unpriced: {token}"
            )

        from decimal import Decimal

        market_cap = Decimal(str(value))
        if market_cap < 0:
            raise ValueError(
                f"trench post-limit market cap is negative: {token}"
            )
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "market_id": market_id,
                "market_source_id": handoff["market_source_id"],
                "market_venue": handoff["market_venue"],
                "post_limit_price_points": 0,
                "post_limit_priced_points": 0,
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "crossed_100k": False,
            }
            summary[token] = current
        current["post_limit_price_points"] += 1
        current["post_limit_priced_points"] += 1
        prior = current["max_market_cap_proxy_usd"]
        prior_block = current["max_market_cap_block"]
        block = int(row["block_number"])
        if (
            prior is None
            or market_cap > Decimal(str(prior))
            or (
                market_cap == Decimal(str(prior))
                and (prior_block is None or block < int(prior_block))
            )
        ):
            current["max_market_cap_proxy_usd"] = str(market_cap)
            current["max_market_cap_block"] = block
        if market_cap >= Decimal("100000"):
            current["crossed_100k"] = True

    missing = sorted(set(by_token) - set(summary))
    if missing:
        raise ValueError(
            "trench frozen handoffs lack post-limit price points: "
            f"{missing[:10]}"
        )
    output = list(summary.values())
    output.sort(key=lambda row: row["token"])
    return output


def merge_trench_lifecycle_market_cap_summaries(
    registry_rows,
    curve_rows,
    post_limit_rows,
) -> list[dict]:
    """Merge complete curve and selected post-LimitReach summaries."""
    from decimal import Decimal

    registry: dict[str, dict] = {}
    for raw in registry_rows:
        row = dict(raw)
        token = str(row["token"]).lower()
        if token in registry:
            raise ValueError(f"duplicate trench registry token: {token}")
        registry[token] = row

    curve: dict[str, dict] = {}
    for raw in curve_rows:
        row = dict(raw)
        token = str(row["token"]).lower()
        if token in curve:
            raise ValueError(f"duplicate trench curve summary: {token}")
        if token not in registry:
            raise ValueError(
                f"trench curve summary has unknown token: {token}"
            )
        if int(row["priced_points"]) != int(row["price_points"]):
            raise ValueError(
                f"trench curve summary has unpriced points: {token}"
            )
        curve[token] = row

    missing_curve = sorted(set(registry) - set(curve))
    if missing_curve:
        raise ValueError(
            "trench full coverage requires a curve price point for every "
            f"launch: {missing_curve[:10]}"
        )

    post: dict[str, dict] = {}
    for raw in post_limit_rows:
        row = dict(raw)
        token = str(row["token"]).lower()
        if token in post:
            raise ValueError(
                f"duplicate trench post-limit summary: {token}"
            )
        launch = registry.get(token)
        if launch is None:
            raise ValueError(
                f"trench post-limit summary has unknown token: {token}"
            )
        if launch.get("limit_reach_block") is None:
            raise ValueError(
                f"trench non-LimitReach token has post-limit summary: {token}"
            )
        if (
            int(row["post_limit_priced_points"])
            != int(row["post_limit_price_points"])
        ):
            raise ValueError(
                f"trench post-limit summary has unpriced points: {token}"
            )
        post[token] = row

    limit_tokens = {
        token
        for token, row in registry.items()
        if row.get("limit_reach_block") is not None
    }
    if set(post) != limit_tokens:
        missing = sorted(limit_tokens - set(post))
        extra = sorted(set(post) - limit_tokens)
        raise ValueError(
            "trench post-limit summary population mismatch: "
            f"missing={missing[:10]} extra={extra[:10]}"
        )

    output = []
    for token in sorted(registry):
        launch = registry[token]
        curve_row = curve[token]
        post_row = post.get(token)
        curve_points = int(curve_row["price_points"])
        curve_priced = int(curve_row["priced_points"])
        post_points = (
            0
            if post_row is None
            else int(post_row["post_limit_price_points"])
        )
        post_priced = (
            0
            if post_row is None
            else int(post_row["post_limit_priced_points"])
        )
        maxima = []
        if curve_row.get("max_market_cap_proxy_usd") is not None:
            maxima.append((
                Decimal(str(curve_row["max_market_cap_proxy_usd"])),
                int(curve_row["max_market_cap_block"]),
            ))
        if (
            post_row is not None
            and post_row.get("max_market_cap_proxy_usd") is not None
        ):
            maxima.append((
                Decimal(str(post_row["max_market_cap_proxy_usd"])),
                int(post_row["max_market_cap_block"]),
            ))
        if maxima:
            max_value = max(value for value, _ in maxima)
            max_block = min(
                block for value, block in maxima if value == max_value
            )
        else:
            max_value = None
            max_block = None

        output.append({
            "token": token,
            "venue": "trench.today",
            "limit_reached": launch.get("limit_reach_block") is not None,
            "curve_price_points": curve_points,
            "curve_priced_points": curve_priced,
            "post_limit_price_points": post_points,
            "post_limit_priced_points": post_priced,
            "price_points": curve_points + post_points,
            "priced_points": curve_priced + post_priced,
            "max_market_cap_proxy_usd": (
                None if max_value is None else str(max_value)
            ),
            "max_market_cap_block": max_block,
            "crossed_100k": (
                bool(curve_row.get("crossed_100k"))
                or bool(
                    post_row is not None
                    and post_row.get("crossed_100k")
                )
            ),
        })
    return output


def validate_trench_source_coverage_report(
    report: Mapping[str, object],
    *,
    required_start_block: int,
    snapshot_head_block: int,
) -> dict:
    """Validate complete curve-plus-selected-market trench.today coverage."""
    if str(report.get("version") or "") != TRENCH_SOURCE_COVERAGE_VERSION:
        raise ValueError("trench.today source coverage version changed")
    if str(report.get("source_id") or "") != "trench_today":
        raise ValueError("trench.today source coverage source changed")
    if str(report.get("source_readiness") or "") != "adapter_ready":
        raise ValueError("trench.today source coverage readiness changed")
    if str(report.get("coverage_status") or "") != "complete":
        raise ValueError("trench.today source coverage is not complete")

    required = _nonnegative(
        report.get("required_start_block"),
        field="required_start_block",
    )
    first = _nonnegative(report.get("first_block"), field="first_block")
    last = _nonnegative(report.get("last_block"), field="last_block")
    snapshot = _nonnegative(
        report.get("snapshot_head_block"),
        field="snapshot_head_block",
    )
    if required != int(required_start_block) or first != required:
        raise ValueError("trench.today source coverage start changed")
    if snapshot != int(snapshot_head_block) or last != snapshot:
        raise ValueError(
            "trench.today source coverage does not reach snapshot"
        )
    if report.get("continuous") is not True:
        raise ValueError("trench.today source coverage is not continuous")
    missing_ranges = report.get("missing_ranges")
    if not isinstance(missing_ranges, list) or missing_ranges:
        raise ValueError(
            "trench.today source coverage has missing ranges"
        )

    tokens = _nonnegative(
        report.get("tokens_discovered"),
        field="tokens_discovered",
    )
    curve_tokens = _nonnegative(
        report.get("curve_tokens_with_points"),
        field="curve_tokens_with_points",
    )
    limit_tokens = _nonnegative(
        report.get("limit_reach_tokens"),
        field="limit_reach_tokens",
    )
    post_tokens = _nonnegative(
        report.get("post_limit_tokens_with_points"),
        field="post_limit_tokens_with_points",
    )
    lifecycle_tokens = _nonnegative(
        report.get("lifecycle_tokens_with_points"),
        field="lifecycle_tokens_with_points",
    )
    curve_points = _nonnegative(
        report.get("curve_price_points"),
        field="curve_price_points",
    )
    post_points = _nonnegative(
        report.get("post_limit_price_points"),
        field="post_limit_price_points",
    )
    points = _nonnegative(
        report.get("price_points"),
        field="price_points",
    )
    priced = _nonnegative(
        report.get("priced_points"),
        field="priced_points",
    )
    if tokens <= 0:
        raise ValueError("trench.today source coverage has no launches")
    if curve_tokens != tokens:
        raise ValueError(
            "trench.today full coverage lacks curve points for every launch"
        )
    if post_tokens != limit_tokens:
        raise ValueError(
            "trench.today full coverage lacks post-limit points for every "
            "LimitReach token"
        )
    if lifecycle_tokens != tokens:
        raise ValueError(
            "trench.today lifecycle summary does not cover every launch"
        )
    if curve_points + post_points != points:
        raise ValueError(
            "trench.today source coverage point accounting drift"
        )
    if priced != points:
        raise ValueError(
            "trench.today source coverage has unpriced points"
        )
    if report.get("handoff_rule_frozen") is not True:
        raise ValueError(
            "trench.today source coverage handoff rule is not frozen"
        )
    if str(report.get("handoff_rule_version") or "") != (
        "trench-limit-same-transaction-after-v1"
    ):
        raise ValueError(
            "trench.today source coverage handoff rule version changed"
        )
    if report.get("blocking_reason") is not None:
        raise ValueError(
            "complete trench.today coverage cannot retain blocking_reason"
        )

    hashes = {}
    for field in (
        "provenance_sha256",
        "event_tape_sha256",
        "registry_sha256",
        "curve_report_sha256",
        "curve_points_sha256",
        "handoff_report_sha256",
        "handoff_manifest_sha256",
        "post_limit_points_sha256",
        "final_summary_sha256",
    ):
        hashes[field] = _sha256(report.get(field), field=field)

    return {
        "version": TRENCH_SOURCE_COVERAGE_VERSION,
        "source_id": "trench_today",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": required,
        "first_block": first,
        "last_block": last,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": tokens,
        "curve_tokens_with_points": curve_tokens,
        "limit_reach_tokens": limit_tokens,
        "post_limit_tokens_with_points": post_tokens,
        "lifecycle_tokens_with_points": lifecycle_tokens,
        "curve_price_points": curve_points,
        "post_limit_price_points": post_points,
        "price_points": points,
        "priced_points": priced,
        "observed_volume_usd": report.get("observed_volume_usd"),
        "handoff_rule_version": (
            "trench-limit-same-transaction-after-v1"
        ),
        "handoff_rule_frozen": True,
        **hashes,
        "blocking_reason": None,
        "snapshot_head_block": snapshot,
    }

