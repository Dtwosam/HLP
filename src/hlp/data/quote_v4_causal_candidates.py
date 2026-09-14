"""Frozen causal Uniswap V4 point-state winners from exhaustive Phase-1 scans.

Run 34883018674 scanned every direct quote/USDG V4 Initialize interval from
PoolManager deployment through each quote asset's first Pons use minus one in
segments no larger than 100,000 blocks. Every discovered PoolKey was then
validated against PoolManager state at the causal block. These records freeze
the deterministic highest-active-liquidity winner for the residual assets that
were previously classified as delayed by the narrow discovery probe.
"""

from collections.abc import Iterable

from hlp.config import UNISWAP_V4_POOL_MANAGER
from hlp.data.quote_v4_causal_history import select_v4_usdg_causal_state_witness


RESIDUAL_CAUSAL_HISTORY_SCAN_RUN_ID = 34883018674
POOL_MANAGER_DEPLOYMENT_BLOCK = 9_070
SELECTION_RULE = "highest_active_liquidity_then_pool_id"

EXHAUSTIVE_CAUSAL_POINT_STATE_CANDIDATES = {
    "0xb1bf26c1d20ff267a4f93550d1e0d06ac40a114b": {
        "symbol": "RIVN",
        "coverage_from_block": POOL_MANAGER_DEPLOYMENT_BLOCK,
        "coverage_to_block": 36_002_594,
        "coverage_complete": True,
        "segment_blocks_max": 100_000,
        "initialize_events": 7,
        "causal_point_states": 6,
        "selection_rule": SELECTION_RULE,
        "activation_liquidity": 25_970_859_276_841,
        "observed_initial_usd_price": "20.00041170941854158674629570",
        "candidate": {
            "pool_id": "0xbc98f7458578286c304a6ced4aa33a562f37805f95c26ad391cf02da46dab99e",
            "currency0": "0x5fc5360d0400a0fd4f2af552add042d716f1d168",
            "currency1": "0xb1bf26c1d20ff267a4f93550d1e0d06ac40a114b",
            "fee": 880_000,
            "tick_spacing": 17_600,
            "hooks": "0x0000000000000000000000000000000000000000",
            "initialize_block": 17_103_170,
        },
    },
    "0x41f4267525a8aff329540ef24fd83d9044758b33": {
        "symbol": "FIG",
        "coverage_from_block": POOL_MANAGER_DEPLOYMENT_BLOCK,
        "coverage_to_block": 52_956_725,
        "coverage_complete": True,
        "segment_blocks_max": 100_000,
        "initialize_events": 40,
        "causal_point_states": 13,
        "selection_rule": SELECTION_RULE,
        "activation_liquidity": 962_439_577_120_207_465,
        "observed_initial_usd_price": (
            "26.058123141853778610507547106346337608883683875134483091538373230949795495231828"
        ),
        "candidate": {
            "pool_id": "0x8d7e57e6fca7c6ed5744549b19f35be72c8004ab6b3d12c9dd972e31994c4ba1",
            "currency0": "0x41f4267525a8aff329540ef24fd83d9044758b33",
            "currency1": "0x5fc5360d0400a0fd4f2af552add042d716f1d168",
            "fee": 5_000,
            "tick_spacing": 50,
            "hooks": "0x0000000000000000000000000000000000000000",
            "initialize_block": 51_939_706,
        },
    },
    "0xcef9027c7d6985b85f0ba431125073529a947a68": {
        "symbol": "BULL",
        "coverage_from_block": POOL_MANAGER_DEPLOYMENT_BLOCK,
        "coverage_to_block": 54_419_646,
        "coverage_complete": True,
        "segment_blocks_max": 100_000,
        "initialize_events": 41,
        "causal_point_states": 9,
        "selection_rule": SELECTION_RULE,
        "activation_liquidity": 404_061_919_866_128_484,
        "observed_initial_usd_price": "9.636236331759708541332443684",
        "candidate": {
            "pool_id": "0x1bda41eb5701e01bb4ff3659e9e614cd92260efa25731ce3d6ee18e1e25e2cd6",
            "currency0": "0x5fc5360d0400a0fd4f2af552add042d716f1d168",
            "currency1": "0xcef9027c7d6985b85f0ba431125073529a947a68",
            "fee": 30_000,
            "tick_spacing": 300,
            "hooks": "0x0000000000000000000000000000000000000000",
            "initialize_block": 51_854_154,
        },
    },
}


def promote_exhaustive_causal_point_state_routes(
    rpc,
    routes: Iterable[dict],
    probe_rows: Iterable[dict],
    *,
    pool_manager: str = UNISWAP_V4_POOL_MANAGER,
) -> list[dict]:
    """Replace residual delayed routes with exhaustively proven causal winners."""
    route_rows = [dict(row) for row in routes]
    source_by_token = {}
    for raw in probe_rows:
        source = dict(raw)
        token = source["quote_token"].lower()
        if token in source_by_token:
            raise ValueError(f"duplicate residual V4 probe row: {token}")
        source_by_token[token] = source

    for token, evidence in EXHAUSTIVE_CAUSAL_POINT_STATE_CANDIDATES.items():
        source = source_by_token.get(token)
        if source is None:
            raise ValueError(f"missing residual V4 probe row: {token}")
        expected_to = int(source["first_launch_block"]) - 1
        if (
            evidence.get("coverage_complete") is not True
            or int(evidence["coverage_from_block"]) != POOL_MANAGER_DEPLOYMENT_BLOCK
            or int(evidence["coverage_to_block"]) != expected_to
            or int(evidence["segment_blocks_max"]) > 100_000
            or evidence.get("selection_rule") != SELECTION_RULE
        ):
            raise ValueError(f"incomplete frozen causal V4 coverage: {token}")

        promoted = select_v4_usdg_causal_state_witness(
            rpc,
            source,
            [dict(evidence["candidate"])],
            pool_manager=pool_manager,
        )
        if int(promoted["activation_liquidity"]) != int(
            evidence["activation_liquidity"]
        ):
            raise ValueError(f"causal V4 winner liquidity changed: {token}")

        replacements = 0
        next_rows = []
        for row in route_rows:
            if row["quote_token"].lower() == token:
                next_rows.append(promoted)
                replacements += 1
            else:
                next_rows.append(row)
        if replacements != 1:
            raise ValueError(
                f"selected V4 routes must contain exactly one residual route: {token}"
            )
        route_rows = next_rows

    route_rows.sort(
        key=lambda row: (
            int(row["activation_block"]),
            row["quote_token"].lower(),
        )
    )
    return route_rows
