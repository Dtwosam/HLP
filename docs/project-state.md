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

The canonical WETH/USDG anchor tape is now complete through the frozen
snapshot head in recovered-promotion run **33972109927**. The promotion reused
only successful artifacts from the original prefix run, the preserved tail
shard, the manifest-gap recovery and the two exact cancelled-gap repairs. It
proved exact continuous block coverage from **8,621,658** through
**54,486,035** with **49** selected source ranges and no unexplained gaps. The
frozen tape contains **21,794,636** price events and SHA-256
`1258f2c85e01f3f62587eeed37c28a30aecb537411b103f451090541a5f225a1`.
Its causal initial WETH/USD value at block **8,621,657** is
`1781.9239264124660124056136394685358486212055749832181614111330385520256580023364`.
The final event lands exactly at snapshot head **54,486,035**. The promotion
made only **8** archive state RPC requests beyond the reused event artifacts.

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

Only **SKHY / 129 launches** remains unresolved in frozen evidence. Its
bounded V4 search is complete through block **52,863,525**, leaving
**1,622,510** blocks to the frozen snapshot head. The cumulative probe already
found one exact SKHY/USDG PoolManager candidate: pool id
`0x8107f97277321f2899eba8d6721411e34cf368c6e24c9f0abb1658733e548601`,
initialized at block **52,798,959** with fee **10,000**, tick spacing **200**
and no hooks. No positive-liquidity swap was observed through the prior search
end.

A second, still-unexecuted resolution path is now staged from the frozen V3
audit: SKHY has one exact Uniswap V3 **SKHY/WETH** candidate,
`0x13f78b235d19141f572986afcaab66ce7744b4ef`, fee **3000**. The bounded
continuation scans only that pool for its first positive-liquidity swap. The
reusable primitive now rejects requests above **100k blocks** and has a
**30-minute** job ceiling. The canonical segmented wrapper uses up to **23
sequential <=100k-block segments** with early stopping, matching the measured
DELL timing class. If it resolves, USD
conversion is deferred until replay and composes each SKHY/WETH swap with the
event-ordered canonical WETH/USDG anchor, avoiding end-of-block lookahead.

SKHY ownership is now fully fail-closed across both possible venues. If the
SKHY/WETH continuation resolves, the canonical split is **25 direct-USDG V3 +
1 delayed SKHY/WETH V3 = 26 V3**, plus **4 V4** routes. If the V3 continuation
instead proves an exhaustive no-route result through snapshot head, the staged
known-pool V4 continuation can promote the frozen SKHY/USDG pool and the
canonical split becomes **25 V3 + 5 V4**. The generic fallback accepts only
those two disjoint ownership modes, requires exactly **30** feedless assets,
requires exactly one SKHY owner, and still requires exactly **25 causal initial
states**. If neither SKHY route resolves, pricing remains incomplete and the
lifecycle universe freeze stays blocked.

Neither ownership mode adds another full-history venue scan: SKHY is simply an
additional address/pool in the already-required V3 or V4 quote scan, so the
frozen **total processed-block geometry** remains unchanged; only response
volume can change. After the measured keyless DELL oracle 500k-block timeout,
the execution partition was tightened again before first execution to
**128 V3 shards** and **128 V4 quote-fallback shards** with max-parallel 2,
about **144k blocks per shard**. Three-digit suffixes preserve numeric merge
order above shard 99. This changes only per-job span and retry safety, not the
canonical full-history block workload.

The V4 continuation path supports fail-closed `known_pool_only` mode. For
SKHY it skips redundant Initialize discovery and scans only Swap logs for the
already-frozen candidate pool ID. The primitive is capped at **100k blocks per
30-minute job**, while the canonical segmented wrapper uses up to **17
<=100k-block segments**, stops as soon as a segment resolves the frozen route,
and can now be promoted directly into the alternate 25/5 canonical ownership
path. Finalization selects the latest completed segment and publishes an
artifact only if SKHY resolved or the scan reached snapshot head with zero
unsearched blocks. A separate archive deployment-boundary probe
proved the SKHY token contract already existed from block **8,691,227**, so
the missing price history is a liquidity/venue-coverage problem rather than a
token-deployment gap. The official Chainlink directory inventory also has no
SKHY/SK hynix near-match, so no feed alias is assumed.

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
22-asset V2 oracle tape and scans only DELL's missing tail. Live run
**33972806063** proved that all four full **500k-block** DELL shards
(000-003) hit the **20-minute** GitHub job ceiling before artifact upload,
with no provider error. Only the final **222,583-block** tail remained small
enough to continue under the old geometry. The canonical delta ceiling is
therefore **100k blocks** per job,
retaining max-parallel 2 and the same fail-closed 23-vs-22 ownership check.
The promotion accepts an optional prior interrupted delta run, validates its
successful shard manifests, and plans only exact uncovered subranges before
emitting the canonical `phase1-pons-stock-oracle-full` artifact.

Resumable promotion run **33974681334** completed successfully on 2026-09-05.
It reused the 22-feed V2 tape plus preserved delta evidence, filled the DELL
tail with **23 exact source ranges**, and published the canonical full-Pons
stock-oracle artifact with:

- **23** stock quote assets total;
- **22** promoted V2 assets + exactly **1** delta asset (**DELL**);
- **9,734** oracle updates;
- initial-state SHA-256
  `9d49662fcbf052cf6165ce0cb9943bc32ea4efb543cfd3d21cbd0c1956623355`;
- update-tape SHA-256
  `1584526e894e3ba343abb906e7ebeac14de548578b44ae7a7eb352bcd31fe944`;
- exact snapshot head **54,486,035**.

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
- V1 global V3 tape: **240 shards**, about **191k blocks each**,
  max-parallel 2, **40-minute** cap;
- V2 global PoolManager V4 tape: **192 shards**, about **144k blocks each**,
  max-parallel 2, **30-minute** cap.

The V1/V3 and V2/V4 full tapes had not yet been executed when the DELL oracle
recovery supplied a stronger keyless timing sample: successful 100k-block DELL
jobs took about **11m40s** end-to-end. The old 358k/432k venue shards were
therefore resized before first execution. All workflows with more than 99
shards now use **three-digit shard suffixes** so lexical artifact ordering stays
identical to numeric block order during stream merges. This changes only
partitioning and runner headroom; the frozen full-history processed-block floors
are unchanged.

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
V2 curve gaps are capped at **50k blocks**. Anchor gap recovery was
initially tested at 150k, but live gap 018 (52,169,619-52,319,618) hit the
20-minute runner cap before artifact upload. Future anchor manifest-gap jobs
are therefore capped at **50k blocks**, and the four-way exact anchor range
helper now rejects ranges above 200k so each subshard is at most 50k.
Transition gap recovery remains at the separately bounded **150k** ceiling.
The unrun full-venue V1/V3, V2/V4 and V3/V4 quote-fallback recoveries instead
use **100k-block** retry jobs with **30-minute** ceilings, matching the stronger
DELL timing evidence while retaining max-parallel 2.

The cancelled anchor tail recovery preserved one successful **716,631-block**
shard (48,752,988-49,469,618) containing **607,932** price events. It completed
in **1,514.118 seconds** with **1,070** RPC requests. Manifest-gap recovery run
**33957294304** is now reusing that shard and plans **34** exact missing jobs
covering **5,016,417** blocks from 49,469,619 through 54,486,035.

The first two measured **150k-block** anchor gaps completed inside the
20-minute recovery bound: gap 000 produced **168,023** events in **1,103.111
seconds** with **1,415** RPC requests, while gap 001 produced **163,019** events
in **1,093.740 seconds** with **1,418** requests. Later gaps **018**
(52,169,619-52,319,618) and **025** (53,219,619-53,369,618) both timed out
before artifact upload, proving that 150k is not uniformly safe. The lower 50k
recovery ceiling is therefore the fail-safe default for future anchor gaps.

Cancelled anchor gaps **018** and **025** were repaired successfully in run
**33970898635** with the reusable four-way exact range helper. Each 150k hole
was split into four ~37.5k subshards with internal max-parallel 2, staying below
the 50k per-worker recovery bound. Recovered-promotion run **33972109927** then
folded those ranges into the canonical anchor artifact and proved end-to-end
continuity, so no further anchor rescanning is required for the frozen Phase 1
snapshot.

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
- an artifact-only market-path freeze stream-filters the already-frozen V1
  V3, V2 curve, graduation/registration and V4 tapes down to the exact
  representative cohort, preserving each token's launch-to-market event path
  without issuing new provider requests;
- a second artifact-only replay uses those exact 10-token events plus the
  frozen anchor/oracle/fallback tapes to materialize every causal token/USD
  price and market-cap point with the same V1/V2 pricing functions used by
  lifecycle eligibility; final representative validation requires its
  per-token point counts, priced/unpriced accounting, maximum market cap and
  maximum block to agree with the lifecycle summaries;
- a resumable Transfer backfill reconstructs exact holder balances/counts and
  fails closed unless every sampled token begins with a launch-time mint;
- GeckoTerminal is used only as independent DEX evidence, never canonical
  history; the client supports pool identity and bounded OHLCV reads. Every
  actual HTTP attempt is now rate-paced, transient 429/5xx responses alone are
  retried, `Retry-After` is honored, permanent HTTP errors fail immediately,
  and the request counter includes retry attempts rather than only successes.
  Rechecked against the live GeckoTerminal API documentation on **2026-09-05**:
  API version `20230203` remains current, the public limit remains approximately
  **10 calls/minute**, and Robinhood network pool pages are currently indexed.
  The client freezes that contract at a 6.1-second minimum request interval;
- a separate bounded Blockscout cross-check can verify exact transaction
  identity and mined block for representative launches plus each distinct
  first/max/last DEX price checkpoint, but it is **supplementary only** while
  GitHub-hosted runners remain known to receive HTTP 403 from Blockscout APIs.
  Its workflow is gated behind an explicit access-reverified input, is capped
  at 40 targets, and reports request/egress counters. If explorer evidence is
  supplied later, representative validation and Phase 1 PASS require complete
  10-token coverage and exact agreement with the GeckoTerminal checkpoint set;
- V1/V2 lifecycle summaries retain separate maxima from actual V3/V4 Swap
  events so an Initialize-only price cannot masquerade as independent trade
  evidence;
- the manual representative DEX cross-check fails on canonical pool/token-pair
  disagreement and selects deterministic first, maximum-USD and last actual
  V3/V4 Swap checkpoints from the frozen detailed priced path. Duplicate roles
  collapse onto one event when a token has fewer than three distinct swaps.
  Each selected block timestamp is resolved with the canonical public RPC and
  every checkpoint must independently fall inside GeckoTerminal's hourly
  OHLCV envelope before the token can be marked matched; the final Phase 1
  acceptance report also verifies nested checkpoint counts and matches.
  Tokens with no DEX swap checkpoint or no registered V4 pool stay explicit
  rather than being silently treated as matched;
- the shared RPC client now measures successful HTTP response bytes and every
  RPC CLI summary reports that egress counter; the manual GitHub-Actions
  accounting workflow aggregates explicit request counters, response bytes,
  reported block ranges, acquisition elapsed time, GitHub job runtime and
  artifact storage rather than estimating provider usage. Historical runs
  created before this instrumentation remain request/storage evidence only;
  response-byte evidence must come from instrumented future or bounded runs;
- an artifact-only representative validation join requires all 10 tokens to
  have consistent lifecycle pricing evidence, detailed launch/trade paths,
  detailed per-event USD price replay, holder replay, pool identity
  reconciliation and multi-point independent DEX price evidence before it can
  publish a complete validation bundle. Blockscout explorer verification is
  accepted as supplementary evidence when access is reverified, but is not a
  required GitHub-hosted dependency while the documented HTTP 403 persists;
- a reusable manual-only `phase1-pons-representative-evidence-chain` now threads
  one completed eligibility parent run through sample freeze, market-path
  extraction, priced-path replay, Transfer/holder reconstruction, the bounded
  GeckoTerminal DEX cross-check and final representative validation. Market-path
  extraction and Transfer acquisition start in parallel after the sample freeze.
  The chain calls the reusable Transfer workflow exactly once. If that matrix
  fails or is cancelled after preserving successful shards, a later
  representative-chain run resumes only missing ranges by supplying the earlier
  parent run as `prior_transfer_run_id`; this avoids discarding completed
  holder work while keeping the reusable-workflow graph fail-closed. The
  reusable Transfer workflow's `workflow_call` contract now carries the same
  frozen **200k-block** default as manual dispatch; an inert caller probe caught
  the previous missing required-input default, and the staged representative
  one-shot now passes GitHub graph validation and skips cleanly until its
  explicit launch phrase is committed. Representative validation now also binds
  the market-path V1/V3 and V2/V4 source run IDs to the lifecycle evidence,
  verifies the canonical registry, V2 curve, transition, quote-audit, anchor,
  stock-oracle and quote-fallback run IDs carried by upstream manifests, and
  persists those source IDs into the final representative validation manifest.
  Inert graph-validation run **33986987191** confirmed the stricter reusable
  input contract compiles without launching representative acquisition.
  Representative validation now also records the exact V1 and V2 lifecycle
  artifact SHA256 values; final Phase 1 acceptance requires those hashes to
  match the lifecycle hashes cryptographically bound into the promoted eligible
  universe, so matching run IDs alone are no longer sufficient. The
  representative sample also binds its five runner tokens exactly to frozen
  research-smoke run **33920762592** and carries the frozen smoke universe SHA
  `4861b2af...9c19ab9` plus outcome SHA `6fb40693...1fc6ef2` into the final
  representative manifest. Phase 1 acceptance freezes that runner-smoke run and
  both full SHA256 values independently, so the >=5x runner proof cannot drift
  behind a valid-looking dynamic sample run. A reusable
  `phase1-pons-post-eligibility-evidence-chain` stages the normal post-crawl
  handoff: it fail-closes on source parent **33982556591**, runs the current-code
  eligible-universe promotion and representative evidence chain under one caller
  run ID, then publishes
  `phase1-pons-post-eligibility-evidence-ready`. Its guarded one-shot watches
  `.github/phase1-pons-evidence-launch.txt`; inert validation run
  **33988716778** skipped cleanly while compiling the nested graph.

The final Phase 1 viability path is also staged fail-closed:

- every RPC acquisition summary reports both response-byte egress and a route
  label; only the canonical Robinhood public RPC and the SolidRPC keyless or
  authenticated-Free routes are accepted as proven-free acquisition evidence;
- a manual artifact-only viability projection consumes measured accounting
  runs and an explicit route plan, then uses the worst observed per-processed-
  work-block request, egress, artifact-storage and runtime rate for each route.
  Repeated ranges inside one job are deduplicated, while overlapping ranges in
  distinct jobs/scans remain separate work units; a global unique-block metric
  is retained separately for audit;
- because the frozen route plan forbids reusing one workflow run ID across
  multiple acquisition routes, the multi-route eligibility parent run is not
  treated as route-separated accounting evidence. A reusable manual-only
  `phase1-pons-viability-route-measurement` workflow now runs exactly one of
  the nine canonical production CLI paths per invocation over an operator-
  supplied **<=50k-block** range, producing one distinct run ID for that route.
  The `pons_registry` measurement is the deliberate exception inside one run:
  it executes V1 and V2 registry scans as two separate jobs over the same
  bounded range so accounting preserves the frozen overlapping-generation
  work geometry instead of deduplicating it. Quote-fallback measurements reuse
  only the canonical V3/V4 route files from a completed eligibility run.
  Current branch orchestration keeps those nine measurements as **nine
  individually guarded workflow runs**, not one matrix/caller run: a shared
  `.github/phase1-pons-viability-ready.json` must first name a successful
  post-eligibility evidence run and
  `.github/phase1-pons-viability-runs.json` must be armed to that same
  evidence run. Each route-specific one-shot then calls
  `phase1-pons-viability-guarded-route` -> the canonical bounded measurement.
  The guard refuses RPC work if the ledger is unarmed, names a different
  evidence run, has a changed route set, or already contains a positive run ID
  for that route; intentional reruns therefore require explicitly clearing the
  route slot first. This preserves the frozen distinct-run-ID contract and
  keeps archive pressure one route at a time. Two no-RPC probes established why more automatic
  branch-only chaining is not used: run **33988308531** received HTTP 404 when
  its branch workflow attempted to dispatch another branch-only workflow with
  `GITHUB_TOKEN`, and successful source probe **33988762949** produced no
  `workflow_run` watcher run because that watcher is not on the default
  branch. A same-push shared-concurrency experiment also cancelled excess
  pending route workflows, so it is not a valid nine-run serializer.
  Completed route IDs are recorded in
  `.github/phase1-pons-viability-runs.json`; the guarded
  `phase1-pons-viability-ledger-finalize-one-shot` independently requires the
  ledger evidence run to equal the armed readiness evidence run, then verifies
  all nine successful route workflow **file paths**, branch, distinct run IDs
  and expected measurement artifacts before passing them to the reusable final
  acceptance chain. Every route must expose its
  `phase1-pons-viability-measurement-<route>-primary` artifact, and
  `pons_registry` must additionally expose its V2 secondary measurement
  artifact.
  Workflow paths are used deliberately because GitHub replaces the run
  `name` field with the custom `run-name` string; inert route run
  **33988929710** demonstrated that distinction before any acceptance evidence
  was collected;
- the frozen heavy-acquisition contract requires exact full-history work-block
  floors for exactly nine routes, totaling **331,011,903 processed
  work-blocks**. The Pons registry floor intentionally counts its overlapping
  V1 and V2 generation scans separately. The frozen routes are Pons registry,
  V1 V3, V2 curve, V2 transition, V2 V4, WETH/USDG anchor, stock oracle,
  V3 quote fallback and V4 quote fallback. The final PASS artifact validates
  and republishes both the exact per-route block map and the total;
- a final manual artifact-only acceptance gate can return
  `hlp-v1-phase1-data-viability` PASS only when the complete eligible universe,
  the 10-token end-to-end validation and all nine instrumented zero-cost route
  projections agree at snapshot head **54,486,035** and share the same V1/V2
  lifecycle evidence. The reusable
  `phase1-pons-final-acceptance-chain` graph has also been validated through
  an inert caller, so its nine distinct measurement IDs can later flow through
  accounting -> viability projection -> acceptance without another reusable-
  workflow contract discovery. The acceptance function independently rechecks
  that route evidence IDs are positive, match each route's declared evidence
  count and are never reused across routes, then republishes the exact
  route-to-evidence-run map in the PASS report. It also freezes the canonical
  representative registry/curve/transition/quote-audit/anchor/oracle source run
  IDs and rejects drift before PASS, so those guarantees do not depend only on
  the orchestration layer.

These are tooling completions, **not Phase 1 acceptance evidence yet**. The
representative sample freeze still waits on canonical V1/V2 lifecycle
eligibility artifacts. Actions history contains no completed
`phase1-pons-v1-v3-full` or `phase1-pons-v2-v4-full` run yet, so those two
full venue tapes remain upstream acquisition blockers alongside the unfinished
pricing inputs. A manual-only
`phase1-pons-full-eligibility-acquisition-chain` now serializes V1 V3 first,
V2 V4 second, then passes same-run artifacts into the pricing/eligibility chain.
If either full venue matrix fails after preserving successful shard artifacts,
the same run invokes its manifest-gap recovery workflow and retries only missing
intervals before continuing. A systemic failure with no reusable artifacts still
stops fail-closed. Within pricing, SKHY V3 runs before the optional SKHY V4
continuation. The
64-shard V3 quote fallback does not start until V3 has resolved SKHY or an
exhaustive V3 miss has been followed by a route-ready V4 result. If either V3
or V4 full quote scan then fails after preserving successful shards, the same
pricing run invokes its manifest-gap recovery and continues only from a
recovered canonical artifact. If neither venue resolves SKHY, the chain stops
before the full fallback scans.
The guarded one-shot launcher remained pinned to oracle promotion run
**33974681334** until that run completed successfully and the archive lane was
clear. It was then fired once at commit
`c53b3a63156976a5873752c332fa7578011249b0`, creating full eligibility
acquisition run **33982556591**. Its stock-oracle preflight passed before any
archive crawl began, proving 23 feeds, the single DELL delta, matching
summary/manifests/checksums, chain 4663 and snapshot head **54,486,035**.
The run has now entered the 240-shard V1/V3 stage with max-parallel 2. V2/V4,
pricing/fallback resolution and lifecycle eligibility remain serialized behind
that stage and its automatic manifest-gap recovery path. The first two V1/V3
shards completed successfully in about 26 minutes each. Artifact/log-only
checkpoint run **33984605170** first accounted those two jobs without issuing
provider requests. A stronger artifact/log-only checkpoint,
**33987497436**, later captured the first **7 successful shards**:
**1,337,711 processed blocks**, **12,360 RPC requests**,
**3,066,837,229 response bytes (2.8562 GiB)**, **9,969,790 artifact bytes**
and **10,436.062 seconds** of reported acquisition time, all through
`solidrpc_keyless_public`. A simple same-density operational extrapolation from
that larger sample is about **423.8k requests**, **97.9 GiB response egress**,
**0.318 GiB compressed artifact storage** and **49.7 hours of two-way-parallel
wall time** for the complete V1/V3 route. These checkpoints are explicitly
non-acceptance evidence because the parent acquisition is still incomplete;
frozen viability still requires its separate bounded route measurement run and
worst-observed-per-block projection.

The current branch also hardens manual rescue beyond the launch commit's
single-wave recovery implementation: V1/V3 and V2/V4 gap recovery now split up
to **480** 100k-block gaps into two **serialized** <=240-job waves, each still
capped at max-parallel 2. That covers even a total V1/V3 loss (~459 retry
intervals) without failing the planner solely on GitHub matrix size. Inert
reusable-workflow probe run **33984733342** skipped cleanly, proving GitHub
accepts both two-wave call graphs. These later branch changes do not mutate the
already-running acquisition pinned to commit
`c53b3a63156976a5873752c332fa7578011249b0`; they are the fail-safe manual
rescue path if that run's original automatic recovery cannot close a large
failure set. A guarded
`phase1-pons-live-venue-rescue-one-shot` launcher is staged against parent
run **33982556591** with separate exact launch phrases for V1/V3 and V2/V4;
its inert creation run **33984797673** skipped cleanly, proving the reusable
rescue graph compiles without issuing provider requests.
 Both lifecycle jobs stream the immutable full-history tapes rather than
materializing them in memory, and their artifact-only replay ceiling is **60
minutes** so multi-GB downloads plus causal replay are not killed by the former
30-minute cap. The canonical V1/V3 and V2/V4 aggregates now remain as virtual
JSONL manifests over ordered shard artifacts instead of publishing another
monolithic full-tape copy. Lifecycle and representative consumers resolve
current, partial and prior-recovery shard files by manifest identity
(block range, record count and SHA), not basename alone, because successive
gap-recovery generations may legitimately reuse compact names such as
`*-gap-000.jsonl`.
The live eligibility parent is pinned to launch commit
`c53b3a63156976a5873752c332fa7578011249b0`, so later branch hardening cannot
change the eligible-universe manifest that parent will eventually emit. Current
code therefore carries an artifact-only
`phase1-pons-eligible-universe-promote` workflow plus a guarded one-shot pinned
to source parent **33982556591**. After the parent completes, promotion
re-downloads its V1/V2 lifecycle artifacts and re-runs only the universe freeze
on current code; it does not issue RPC requests. The promoted universe manifest
cryptographically binds the exact V1 and V2 lifecycle artifact SHA256 values,
and the final acceptance function requires those hashes to agree with the
freeze summary before PASS. Inert launcher run **33987410394** skipped cleanly,
proving the reusable promotion graph compiles without touching the archive
lane. The normal supported path wraps that promotion together with representative
reconstruction in the post-eligibility evidence chain described above, so its
single successful caller run ID contains both
`phase1-pons-eligible-universe` and
`phase1-pons-representative-validation`. The standalone promotion and
representative launchers remain recovery/debug fallbacks.

An artifact/GitHub-metadata-only `phase1-pons-readiness-audit` now provides
one fail-closed state machine across the remaining Phase 1 handoffs:
eligibility acquisition -> post-eligibility evidence -> nine viability routes
-> final acceptance -> PASS. It validates frozen run IDs, required artifact
sets, exact viability workflow file paths, distinct route-run IDs and the
presence of the actual `phase1-pons-acceptance-gate` artifact before it can
report Phase 1 complete. It also reads the source run's job matrix so GitHub's
top-level reusable-workflow `queued` state cannot be mistaken for a failure.
Real audit run **33989828191** completed successfully and classified the live
parent as `eligibility_acquisition` with next action
`wait_for_full_eligibility_acquisition`, **0 failed jobs**, 2 in-progress
jobs and no premature evidence/viability readiness claim. The audit's
finalizer lookup is intentionally bounded and skipped until an evidence run
and all nine route IDs exist, avoiding branch histories with >1,000 workflow
runs.

A final artifact-only `phase1-pons-pass-closeout-one-shot` is staged but
unarmed. After the ledger finalizer produces a real PASS artifact and that run
is recorded in `docs/project-state.md`, closeout verifies the exact
`phase1-pons-acceptance-gate` report, frozen snapshot/route/work-block
contract, successful ledger-finalizer workflow path, git ancestry, and PR #3
identity (`phase1/data-acquisition-spike` -> `main`). It fails if code changed
after the PASS-producing commit; only the project-state PASS record and the
closeout config are allowed post-PASS changes. It also requires every Phase 1
gate checkbox to be complete and PR #3 to remain open/draft at audit time.
Only a successful closeout artifact can declare it safe to mark the PR ready
and merge after required checks. Inert graph-validation run **33991433159**
skipped cleanly, so no closeout or merge action has been taken.

The egress projection additionally needs instrumented measured runs;
older completed runs cannot retroactively provide response-byte counters. No
representative validation, viability projection or acceptance artifact should
be counted as complete until those upstream frozen inputs and measurements
exist.

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
