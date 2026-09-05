# HLP Project State

Updated: 2026-09-05
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

The canonical full V2 bonding-curve tape is now complete through the same frozen
snapshot head in recovery run **33936232604**. The manifest-gap merge closed
every block interval exactly and published `phase1-pons-v2-curve-full` with:

- **9,231,724** total curve events;
- **4,949,167** buys;
- **4,277,267** sells;
- **5,290** buybacks;
- **182,738** curves with observed activity out of 225,951 registry curves;
- **112** source files merged with strict event ordering and block continuity;
- tape SHA-256:
  `771c9147ef1a84bd673532842972e16e0ee12cae1513a41b402f53b5c444c50b`.

The full V2 transition control tape had already completed successfully in run
**33912452330** at the same snapshot head. It contains **3,638** graduations
and **3,638** registrations for the same 3,638 tokens, with zero graduated
tokens lacking a registration and zero registered tokens lacking a graduation.
The frozen transition SHA-256 values are
`492aa1bfd325050395727255b5de93c88935cf8e40bd580256ce69f9b3427f5e`
for graduations and
`8cc55b761e10c8643a907389602ca5f7790bd7df99cee2d00fbe120a9cd40e93`
for registrations.

### Lifecycle boundary completeness

- [x] V1 Uniswap V3 Initialize is retained as a price point rather than starting at first swap
- [x] V1 smoke proved 166 launches -> 166 exact Initialize events plus 114,042 swaps
- [x] V2 Uniswap V4 Initialize is retained separately from PoolGraduated and first V4 swap
- [x] V2 smoke proved 1 registration -> 1 exact Initialize plus 788 swaps
- [x] curve -> V4 Initialize -> PoolGraduated seed -> first V4 swap ordering is preserved explicitly
- [x] refreshed 100k-block research cohort still has 5 eligible tokens (4 V1, 1 V2)
- [x] refreshed cohort preserves continuous upside; all 5 eligible tokens have at least one later 5x point and the largest observed later multiple remains about 159.8x

### Quote-asset completeness

The complete registry contains 57 Pons quote assets. Direct official Chainlink
coverage plus cbBTC's verified crypto/USD feed does not cover every Robinhood
Stock Token used by Pons. The official Chainlink Robinhood directory inventory
contained 54 total feed records at audit time and genuinely omitted 30 Pons
Stock Token symbols; this is not treated as a parser failure. The frozen quote
audit proves all 30 missing-feed assets are used by **V2 only**; none appear in
V1 launches. Therefore V1 eligibility does not depend on the V3/V4 quote
fallback chain.

A causal Uniswap V3 fallback audit at each quote's first Pons use proved:

- 25 of those 30 feedless Stock Tokens already had direct USDG V3 liquidity;
- those 25 routes cover **17,312 Pons launches**;
- route discovery used current immutable V3 factory mappings, then required
  pool code, initialized state and positive active liquidity at
  first-Pons-use minus one before accepting a route;
- all 25 selected V3 routes are direct USDG, so their historical fallback tape
  does not depend on the separate WETH/USDG anchor.

The five V3 misses were then checked against Sushi V3 and bounded Uniswap V4
history. Sushi had no candidate pools. Uniswap V4 produced delayed direct-USDG
routes for TTWO, RIVN and BULL, covering another **3,744 launches**:

- TTWO first positive-liquidity V4 swap: block **36,023,158**;
- RIVN first positive-liquidity V4 swap: block **36,042,806**;
- BULL first positive-liquidity V4 swap: block **54,451,385**.

These are delayed routes, not evidence that the quote was priceable at first
Pons use, so the earlier intervals remain explicitly partial. A non-overlapping
500,000-block V4 continuation then resolved FIG as well. The measured V4
fallback now covers **3,870 launches across 4 of the 5 original V3 misses**.

Only **SKHY / 129 launches** remains unresolved. Its bounded V4 search is
complete through block **52,863,525**, leaving **1,622,510** blocks to the
frozen snapshot head. The cumulative probe already found one exact SKHY/USDG
PoolManager candidate: pool id
`0x8107f97277321f2899eba8d6721411e34cf368c6e24c9f0abb1658733e548601`,
initialized at block **52,798,959** with fee **10,000**, tick spacing **200**
and no hooks. No positive-liquidity swap was observed through the prior search
end.

The V4 continuation path now supports a fail-closed `known_pool_only` mode.
For SKHY this skips redundant future Initialize discovery and scans only Swap
logs for already-frozen candidate pool IDs, roughly halving the remaining
log-query shape versus the generic discovery continuation. It refuses that
mode when an unresolved row has no existing candidate. A separate archive
deployment-boundary probe proved the SKHY token contract already existed from
block **8,691,227**, so the missing price history is a liquidity/venue-coverage
problem rather than a token-deployment gap. The official Chainlink directory
inventory also has no SKHY/SK hynix near-match, so no feed alias is assumed.

V3 and V4 fallback tapes remain venue-specific for provenance, then merge into
one disjoint generic quote/USD fallback artifact before both V1 and V2
lifecycle replay. Chainlink and DEX fallback ownership is also checked for
overlap and fails closed.

The frozen full-Pons quote audit in run **33923299711** contains **23**
Chainlink-priced stock quote assets. The earlier successful V2 oracle tape in
run **33912985322** already covers **22** of those assets and 9,530 oracle
updates. Artifact-level comparison proves the only missing current full-Pons
stock feed is **DELL** quote token
`0x941ae714ec6d8130c7b75d67160ca08f1e7d11dd`, used by **223** Pons launches
from block **52,263,453**. Its Chainlink feed
`0x1c6c8cadbe02e19129c39ddb92281ce4c0bf206b` resolves to aggregator
`0xd6ed4e7d4aba1111eb42a349899b5c72ee1c9fef` and is causally ready at block
**52,263,452**. The reusable
`phase1-pons-stock-oracle-promote-v2-delta` workflow therefore promotes the
22-asset V2 oracle tape and scans only DELL's missing tail, split into
**<=500k-block** jobs, before emitting the canonical
`phase1-pons-stock-oracle-full` artifact. It fails closed unless the frozen
23-vs-22 coverage relationship and exact merged stock-feed ownership still
hold.

A separate causality fix activates staggered quote-source state only at each
asset's first Pons use. Future oracle availability is never active from the
beginning of a historical replay. Lifecycle summaries distinguish
`eligible`, `ineligible` and `unknown`: a later priced >=$100k point proves
eligibility even if an earlier interval was unpriced, while a non-crossing
partial history remains unknown and blocks final universe freeze.

## Backfill execution guardrail

Full-history Pons backfills are manual-only workflows. Code/workflow pushes must
not auto-launch archive matrices. Dependency run IDs are workflow-dispatch
inputs rather than reasons to edit workflow YAML. Heavy jobs fail fast when a
required artifact is unavailable; runner-side polling is forbidden.

Measured recovery behavior on the keyless archive route showed that dense
716k–864k block shards can hit the 30-minute GitHub job limit even though the
RPC path is healthy. The full-history definitions were therefore resized
without increasing concurrent RPC pressure:

- V2 curve: 64 shards, about 432k blocks each, max-parallel 2, 25-minute cap;
- WETH/USDG anchor: 128 shards, about 358k blocks each, max-parallel 2,
  25-minute cap;
- V1 global V3 tape: 128 shards, about 358k blocks each, max-parallel 2,
  25-minute cap;
- V2 global PoolManager V4 tape: 64 shards, about 432k blocks each,
  max-parallel 2, 25-minute cap.

Two reusable manual-only range recovery workflows split a bounded exact
failed curve or anchor interval into four smaller subshards and merge only that
interval. They reject spans above 200k blocks for V2 curves or 600k blocks for
the anchor, keeping their four subshards within the same 50k/150k retry
ceilings used by manifest-gap recovery.
On top of those primitives, manifest-driven gap recovery now reads every
successful partial-run manifest, derives the exact uncovered block intervals,
and creates only bounded retry jobs. V2 curve, WETH/USDG anchor, V2 transition
and V2 PoolManager V4 recovery all have reusable gap-aware workflows. Each can
reuse successful gap artifacts from one earlier interrupted gap-recovery run,
so completed retry work survives another cancellation. Recovery planners also
fail fast above **240 matrix jobs**, below GitHub Actions' matrix ceiling, rather
than generating an invalid oversized matrix from an excessively small manual
gap size. A live recovery measurement on 2026-09-05 showed that 200k-block V2
tail jobs at the first two missing ranges both reached the 20-minute job cap, so
V2 curve gaps are now capped at **50k blocks**. Anchor, transition and V4 gap
workflows currently use a conservative **150k-block** ceiling until separately
measured.

The cancelled anchor tail recovery preserved one successful **716,631-block**
shard (48,752,988-49,469,618) containing **607,932** price events. It completed
in **1,514.118 seconds** with **1,070** RPC requests. Manifest-gap recovery run
**33957294304** is now reusing that shard and plans **34** exact missing jobs
covering **5,016,417** blocks from 49,469,619 through 54,486,035.

The first two measured **150k-block** anchor gaps both completed inside the
20-minute recovery bound: gap 000 produced **168,023** events in **1,103.111
seconds** with **1,415** RPC requests, while gap 001 produced **163,019** events
in **1,093.740 seconds** with **1,418** requests. That validates the current
150k retry size on the keyless route, but it is close enough to the job limit
that the cap is not increased. The stabilized adaptive log scanner is shared
by this path too.

The same V2 tail exposed a request-shape inefficiency in adaptive `eth_getLogs`
scanning: after shrinking a rejected window, the iterator immediately doubled
again after one success, which can oscillate on dense log ranges. It now waits
for eight consecutive successful windows before probing larger. The first two
optimized 50k jobs completed with **466** and **474** RPC requests; the
neighboring pre-change 50k success needed **804**. This is request-efficiency
evidence, not a direct wall-clock benchmark, because event density and provider
latency differ by range.

The final merge proves strict block continuity against the preserved prefix
before publishing the canonical full tape.
Successful historical shards are never re-fetched just because a later dense
range timed out.

The gap recovery workflows and the bounded V4 quote continuation expose both
`workflow_dispatch` and `workflow_call`, but no push trigger. Temporary
one-shot wrappers may invoke the tested reusable logic when direct workflow
dispatch is unavailable; wrappers are sequenced one heavy recovery at a time
and are removed after use.

This keeps normal development/tests responsive while long archive shards run,
and prevents accidental backfills from competing for GitHub-hosted runner
capacity. Secondary network/integration smokes are manual-only; the fast
unit/compile suite remains automatic on pushes. This prevents a CLI or shared
source edit from faning out into many unrelated RPC jobs and starving bounded
research probes.

The complete downstream eligibility paths are now explicitly staged as:

- shared: full Pons registry -> quote audit -> Chainlink/cbBTC oracle +
  venue-specific V3/V4 quote fallbacks -> one disjoint generic quote/USD tape,
  plus the WETH/USDG anchor where lifecycle pricing requires it;
- V1: full registry -> globally scanned/filter-local V3 tape -> Chainlink USD
  replay -> summary-only lifecycle eligibility -> frozen >=$100k V1 subset;
- V2: V2 registry -> curve/transition -> V4 tape -> Chainlink + generic
  fallback USD replay -> summary-only lifecycle eligibility -> frozen >=$100k
  V2 subset;
- final: fail closed only while any lifecycle remains eligibility-unknown;
  proven eligible histories may contain earlier unpriced intervals, then union
  the known V1 + V2 eligible tokens into the immutable all-Pons >=$100k
  research universe.

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

## Representative Phase 1 validation tooling

The representative-token acceptance path is now staged without changing any
research threshold or starting another archive crawl:

- a deterministic freeze selects exactly five measured >=5x runners and five
  lifecycle failures, with both Pons generations represented;
- a resumable Transfer backfill reconstructs exact holder balances/counts and
  fails closed unless every sampled token begins with a launch-time mint;
- GeckoTerminal is used only as independent DEX evidence, never canonical
  history; the client supports pool identity and bounded OHLCV reads;
- V1/V2 lifecycle summaries retain separate maxima from actual V3/V4 Swap
  events so an Initialize-only price cannot masquerade as independent trade
  evidence;
- the manual representative DEX cross-check fails on canonical pool/token-pair
  disagreement, derives the frozen token/USD price at each available swap-only
  checkpoint from the lifecycle market-cap proxy and launch supply, resolves
  the exact block timestamp with the canonical public RPC, and requires that
  price to fall inside GeckoTerminal's independent hourly OHLCV envelope;
  tokens with no DEX swap checkpoint or no registered V4 pool stay explicit
  rather than being silently treated as matched;
- a manual GitHub-Actions accounting workflow measures reported request
  counters and artifact bytes rather than estimating provider usage;
- an artifact-only representative validation join requires all 10 tokens to
  have consistent lifecycle pricing evidence, holder replay, pool identity
  reconciliation and explicit DEX price-cross-check state before it can
  publish a complete validation bundle.

These are tooling completions, **not Phase 1 acceptance evidence yet**. The
representative sample freeze still waits on canonical V1/V2 lifecycle
eligibility artifacts, which in turn remain blocked on the unfinished pricing
inputs. No representative transfer backfill or DEX validation artifact should
be counted as complete until those upstream frozen inputs exist.

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
