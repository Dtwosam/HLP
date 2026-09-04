# HLP Project State

Updated: 2026-09-04
Repository: Dtwosam/HLP
Current phase: Phase 1 — Historical/Live Data Acquisition Spike
Status: ACTIVE
Next phase: Phase 2 — Pons Universe & Outcome Dataset (LOCKED until Phase 1 PASS)

## Frozen user requirements

- Robinhood Chain only.
- Pons-launched tokens are the primary research universe; non-Pons launchpads are secondary/background only.
- Include a Pons token if it reaches at least $100,000 market-cap proxy at any point in its complete observed lifecycle.
- The only precommitted positive threshold is >=5x after the first major dump.
- Do not predefine what counts as a major dump; derive/test candidate dump thresholds from historical data.
- 5x is the minimum, not the target/cap.
- Preserve full upside magnitude so 10x/20x/50x+ runners remain distinct outcomes.
- Do not pre-assume holder/wallet/volume/liquidity/chart signals.
- Derive predictive patterns from the studied population.
- End product is a live comeback/buy-signal ranking tool.
- Live coins continue becoming future training data.
- Production-model updates are controlled champion/challenger promotions.
- Development/data/infrastructure must remain $0.

## Phase 0 — PASS

Source-of-truth PR #2 was merged to main at:
- `10ba7dc07f4f830211a2da70bac0327f8085dd87`

The master spec, build order, anti-leakage standard and $0 rules are frozen.

## Phase 1 — verified foundation

### Live/current chain access
- [x] official Robinhood public RPC reports chain ID 4663
- [x] current block/header access
- [x] bounded current eth_getLogs
- [x] current bytecode verified for Pons V1/V2 factories
- [x] current bytecode verified for Pons V2 meme hook and Uniswap V4 PoolManager
- [x] official public RPC proven pruned for older historical state

### Protocol decoding
- [x] Pons V1/V2 launch event decoding
- [x] Pons V2 CurveBuy/CurveSell decoding
- [x] Uniswap V3 Swap decoding
- [x] Uniswap V4 Swap decoding
- [x] Pons V2 PoolRegistered token/pool bridge
- [x] ERC-20/state helpers
- [x] deterministic V3/V4/curve price and market-cap-proxy math
- [x] immutable JSONL snapshot + SHA-256 provenance manifests

### Historical/archive access
- [x] SolidRPC keyless Robinhood route reachable from HLP's GitHub runner
- [x] SolidRPC route successfully read Pons V1 bytecode at block 30,000,000
- [x] SolidRPC route successfully returned historical Pons launch logs
- [x] Pons protocol generation set frozen as **V1 + V2**; Uniswap V3/V4 are downstream trading venues, not extra Pons generations
- [x] legacy V1-ABI factory `0x0c37...77a4`: exact first-code block **8,600,612**, first raw-chain launch **8,621,658**
- [x] primary V1-ABI factory `0xa5aa...1feb`: exact first-code block **8,991,118**, first raw-chain launch **9,019,252**
- [x] current V1-ABI factory `0xf4fc...eb75`: exact first-code block **39,010,564**, first raw-chain launch **39,497,847**
- [x] V2 factory `0x7ed5...ec7e`: exact first-code block **26,841,846**, first raw-chain launch **27,027,321**
- [x] all four factory deployments verified with direct archive RPC bytecode + raw TokenLaunched decode at audit head **54,478,341**
- [x] generic adaptive eth_getLogs range splitting
- [x] request pacing and Retry-After-aware HTTP 429 handling
- [x] archive API-key support through headers rather than committed URLs
- [x] Blockscout legacy + V2 APIs tested and rejected as GitHub acquisition routes (HTTP 403)
- [x] BlockReq public endpoint rejected for archive history
- [x] NodeFlare public endpoint unsuitable from shared GitHub runner (HTTP 429)
- [x] hoodexplorer client implemented but provider unreachable from current runner

## Current preferred zero-cost acquisition architecture

**Live/head:** official Robinhood public RPC (plus later WebSocket/Alchemy if needed).

**Historical archive:** SolidRPC Robinhood archive.

Verified provider facts at 2026-09-04:
- keyless public Robinhood route works from our runner;
- public eth_getLogs maximum range is 2,000 blocks;
- authenticated Free plan is $0, no card required;
- Free allowance is 10,000 RPC method calls per UTC day;
- Robinhood uses archive nodes on the Free plan;
- authenticated route removes the public 2,000-block policy cap; practical ranges are still discovered adaptively.

Secrets are never committed. No archive key is currently configured in the GitHub runner, so the verified acquisition path is the keyless public archive route. HLP automatically switches to the authenticated Free endpoint if a key is later provided.

## Measured Pons full-history backfill

Frozen registry snapshot head: **54,486,035**.

The complete same-head Pons registry recovery finished successfully in run
**33911022718** and is now frozen as the canonical Phase 1 launch registry:

- **494,639 total Pons launches**;
- **268,688 V1 launches**;
- **225,951 V2 launches**;
- V1 factories: 1,895 legacy + 266,221 primary + 572 current;
- **57 unique pair-token addresses**;
- registry SHA-256:
  `c75b93b5b8ace0caad3376b5e79c6dcdb9ba675fce9085f6db7458f3694d30ed`.

The merge proved exact shard block continuity, unique tokens within each
generation, zero V1/V2 token overlap, exact manifest record counts and exact
snapshot-head closure. The immutable recovered artifact is
`phase1-pons-full-registry-recovered`.

Measured V2 registry storage remains small relative to lifecycle tapes. Raw V3,
V4 and anchor price events are expected to dominate Phase 1 storage.

### Lifecycle boundary completeness

- [x] V1 Uniswap V3 Initialize is retained as a price point rather than starting at first swap
- [x] V1 smoke proved 166 launches -> 166 exact Initialize events plus 114,042 swaps
- [x] V2 Uniswap V4 Initialize is retained separately from PoolGraduated and first V4 swap
- [x] V2 smoke proved 1 registration -> 1 exact Initialize plus 788 swaps
- [x] curve -> V4 Initialize -> PoolGraduated seed -> first V4 swap ordering is preserved explicitly
- [x] refreshed 100k-block research cohort still has 5 eligible tokens (4 V1, 1 V2)
- [x] refreshed cohort preserves continuous upside; all 5 eligible tokens have at least one later 5x point and the largest observed later multiple remains about 159.8x

### Quote-asset completeness

V1 and V2 now target one all-Pons causal Stock Token/USD oracle tape derived
from the complete 494,639-launch registry. The full registry exposed current
Chainlink directory naming variants, so feed discovery accepts both official
`Robinhood TICKER / USD` and `Robinhood TICKER-USD` forms while still
requiring exact Robinhood-chain records. Unknown or genuinely feedless quote
assets remain explicit blockers; they are never assigned a guessed USD price.

## Backfill execution guardrail

Full-history Pons backfills are manual-only workflows. Code/workflow pushes must
not auto-launch archive matrices. Dependency run IDs are workflow-dispatch
inputs rather than reasons to edit workflow YAML. Heavy jobs fail fast when a
required artifact is unavailable; runner-side polling is forbidden.

This keeps normal development/tests responsive while long archive shards run,
and prevents accidental backfills from competing for GitHub-hosted runner
capacity.

The complete downstream eligibility paths are now explicitly staged as:

- shared: full Pons registry -> quote audit -> all-Pons Stock Token oracle +
  WETH/USDG anchor;
- V1: full registry -> globally scanned/filter-local V3 tape -> summary-only
  lifecycle eligibility -> frozen >=$100k V1 subset;
- V2: V2 registry -> curve/transition -> V4 tape -> summary-only lifecycle
  eligibility -> frozen >=$100k V2 subset;
- final: fail closed on unpriced lifecycles, then union V1 + V2 eligible tokens
  into the immutable all-Pons >=$100k research universe.

## Query-efficiency design

Do not issue one historical API query per coin unless unavoidable.

Planned high-level scans:
1. factory launch events -> token/curve/pool registry;
2. Pons V2 CurveBuy + CurveSell by global topic scans, then filter addresses against known Pons curves;
3. Uniswap V4 swaps from the single PoolManager with registered Pons pool IDs pushed into indexed topic1 server-side filters;
4. V3 Initialize/Swap through block-sharded global topic scans followed by frozen Pons V1 pool membership locally; the 268,688-pool V1 registry is too large to push as one RPC address filter;
5. first-pass price/mcap reconstruction keeps eligibility evidence for the full launch population without doing holder/wallet backfills;
6. only after the $100k universe is known, fetch complete market/transfer history for eligible tokens to reconstruct wallet and historical holder state.

This sequencing prevents transfer/holder backfills for the overwhelming majority of coins that never become research-eligible.

## Phase 1 remaining gates

- [x] verify every relevant Pons generation/factory from raw chain
- [x] prove the canonical WETH/USDG V3 USD anchor predates Pons (anchor first-code block **1,506,281**)
- [x] build and freeze the complete historical Pons launch registry through one immutable snapshot head
- [ ] build the complete historical Pons $100k+ eligible universe across V1/V2 full lifecycles
- [ ] benchmark wide authenticated Free eth_getLogs ranges if/when a Free key is configured; keyless sharding remains the required fallback
- [ ] reconstruct >=10 representative Pons tokens end-to-end
- [ ] cross-check reconstructed launch/trade/price paths against independent DEX/explorer evidence
- [ ] quantify full-history request and storage requirements
- [ ] prove the complete Pons + required downstream DEX acquisition plan remains within $0
- [ ] record Phase 1 PASS and merge PR #3

Phase 2 stays locked until these pass.

## Deferred decisions

- exact first-major-dump algorithm;
- exact chronological research split dates;
- exact discovered feature set;
- exact model family;
- exact production signal threshold;
- exact notification/dashboard surface;
- any future automated execution.
