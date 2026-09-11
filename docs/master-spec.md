# HLP V1 — Master Specification

Status: BASELINE v0.1
Date: 2026-09-04
Repository: Dtwosam/HLP
Budget: $0
Chain: Robinhood Chain mainnet, chain ID 4663

## 1. Product mission

HLP finds Robinhood Chain memecoins that have already suffered their first major selloff and whose live behavior begins to resemble historical coins that later produced unusually large recoveries.

The immediate product is a ranked, explainable signal system. It is not an automatic trading system.

## 2. Core research question

Among Robinhood Chain speculative tokens that reached at least $100,000 market-cap proxy, what information was observable during or after the first major dump that separated future comeback runners from otherwise similar coins that failed?

HLP must discover that answer from data rather than hard-code a narrative.

## 3. Universe

### Included

Permissionless/speculative fungible tokens on Robinhood Chain that:

1. can be priced from an observed on-chain market;
2. have reconstructable supply/price history; and
3. reached at least $100,000 market-cap proxy at any point.

Launch origin is recorded, not used as an inclusion shortcut. Pons V1/V2, direct Uniswap launches and other material launch venues are all eligible once adapters exist.

### Deterministic exclusions

Exclude canonical non-memecoin assets using address identity, not symbol/name:

- WETH;
- USDG;
- Robinhood Stock Tokens and ETFs from Robinhood’s canonical registry/API;
- known LP/position tokens;
- protocol/system/bridge infrastructure tokens where classification is deterministic.

Any broader asset-class exclusion requires a decision-log amendment.

## 4. Market-cap threshold

For arbitrary ERC-20 memecoins, a trustworthy historical circulating-supply feed generally does not exist.

HLP therefore uses a reproducible chart market-cap proxy:

market_cap_proxy_usd = point_in_time_token_price_usd × point_in_time_total_supply

For fixed-supply memecoins this behaves like the FDV-style “market cap” traders commonly see on DEX tools.

Third-party marketCap/FDV values are cross-checks, not canonical labels.

## 5. Comeback outcome

### Positive minimum

A qualifying comeback must later offer at least a 5x opportunity after the first major dump.

5x is only the minimum label boundary.

### Continuous outcomes retained

For every coin, retain at minimum:

- max_post_dump_multiple;
- maximum forward market cap;
- time to 2x, 3x, 5x, 10x and later configurable multiples;
- maximum adverse excursion from each candidate signal point;
- time from dump completion to recovery milestones;
- eventual failure/death state where definable.

The model may later learn that the conditions preceding 20x+ runners differ from ordinary 5x runners.

## 6. First-major-dump definition

No arbitrary percentage threshold is frozen in Phase 0.

Phase 2 must study price paths and define a deterministic, point-in-time-compatible event detector for:

initial expansion -> first material drawdown -> completed/confirmed first major dump.

The detector may use change points, drawdown structure, local extrema, liquidity-normalized movement, duration or other empirically justified rules.

The detector is frozen before predictive feature/model discovery begins.

A historical trough used for outcome measurement may be known only after the fact; the live signal timestamp must use a confirmation state that could actually have been known then.

## 7. Canonical data

Canonical facts come from Robinhood Chain itself:

- blocks and timestamps;
- contract creation and protocol launch events;
- ERC-20 Transfer events;
- AMM/curve swaps;
- liquidity events;
- totalSupply/decimals and other state reads;
- creator/deployer/factory relationships;
- transaction senders, recipients and call context where available.

Third-party APIs are allowed for discovery, verification and enrichment, but no critical label should depend on an opaque vendor field if it can be reconstructed on-chain.

## 8. Price reconstruction

HLP reconstructs prices from protocol swap/curve state and verified quote-asset USD anchors.

Price logic is protocol-specific and versioned.

For multi-pool tokens, the canonical price series must use a deterministic liquidity/quality rule frozen in the data contract. Cross-pool arbitrage must not produce double-counted volume.

USD conversion prioritizes verifiable on-chain quote paths and canonical asset/oracle identity. Exact pricing routes are frozen only after Phase 1 validation.

## 9. Candidate feature families

These are research inputs, not assumed signals:

- price path and drawdown structure;
- volume and trade intensity;
- unique buyers/sellers;
- repeat-buy/repeat-sell behavior;
- cohort retention;
- holder count and concentration;
- supply redistribution;
- creator/deployer activity;
- early-wallet behavior;
- wallet funding/relationship graph;
- net flows;
- buy/sell size distribution;
- price impact and sell absorption;
- liquidity/depth changes;
- contract-vs-EOA participation;
- launch mechanics;
- protocol/venue;
- market-wide Robinhood Chain regime;
- timing and lifecycle age.

Point-in-time social features are deferred unless a genuinely free, reproducible historical source is proven.

## 10. Modeling objective

HLP is a ranking/probability system, not a binary oracle.

Initial supervised objectives may include:

- calibrated probability of eventually reaching >=5x after the first major dump;
- ranking by expected/quantile max_post_dump_multiple;
- time-to-event/survival targets;
- false-positive filtering.

Simple baselines are mandatory before complex ML.

The production score and trigger threshold are learned from validation data, not chosen in Phase 0.

## 11. Signal output

A live record should eventually contain:

- token/address;
- timestamp/block;
- current market-cap proxy;
- first-dump state;
- comeback score/probability;
- historical-neighbor/sample context;
- model version;
- top point-in-time feature contributions;
- candidate entry region/condition if the research supports one;
- invalidation/risk reference if empirically supported;
- data-quality/coverage flags.

The system may say NO SIGNAL indefinitely. Scarcity is acceptable.

## 12. Continuous learning

Live tracking never stops at signal issuance.

Each eligible token remains observed so HLP can record its full path and eventual label.

Learning loop:

historical baseline -> live shadow predictions -> immutable outcomes -> new labeled cohort -> challenger retraining -> frozen out-of-sample comparison -> champion promotion only if better.

No single coin can directly rewrite production rules.

## 13. Evaluation

Final promotion uses chronological unseen data and walk-forward simulation.

At minimum report:

- number of eligible coins;
- base rate of >=5x outcomes;
- signals emitted;
- precision at signal threshold;
- recall/coverage;
- PR-AUC and calibration where meaningful;
- 2x/3x/5x/10x+ forward hit rates;
- distribution of max_post_signal_multiple;
- maximum adverse excursion;
- time to milestones;
- false positives;
- performance by launch source, month/regime and liquidity/market-cap band;
- stability under reasonable data/fee/slippage sensitivity assumptions.

No model is accepted solely because it predicts famous historical winners.

## 14. Technology direction

Research/core:
- Python 3.12+
- DuckDB
- Parquet
- Polars and/or Pandas
- NumPy
- scikit-learn
- optional LightGBM/XGBoost only if justified

Ingestion:
- Substreams/Firehose candidate for bulk history and head streaming;
- protocol-specific decoders/adapters;
- Alchemy free archive/WebSocket for targeted state, enrichment and live fallback;
- Robinhood public RPC and Blockscout for verification/fallback.

Storage:
- bulk historical facts/features: local compressed Parquet + DuckDB;
- live operational state: local database first;
- Supabase Free may be added later for compact signal/outcome state if it remains within free limits.

CI:
- GitHub Actions on the public repository.

## 15. Cost policy

Canonical V1 must be operable at $0.

The architecture may use free tiers, but not in a way that silently turns into paid overage.

The unresolved Phase 1 risk is full-history bulk acquisition. Alchemy Free restricts Robinhood eth_getLogs queries to 10 blocks. The Graph Market Free has finite processed-block/egress allowances. A second promising path, hoodexplorer, documents keyless indexed event logs plus an archive-node proxy, but GitHub-hosted runners could not route to it during the first network spike.

Phase 1 must measure a complete-enough historical path from a reachable runtime. Until that passes, full historical acquisition is a viability question, not an assumed solved problem.

## 16. Explicit non-goals for V1

- automated swaps;
- private-key handling;
- guaranteed profit;
- Solana/Base/BNB support;
- paid data feeds;
- paid cloud hosting;
- X/Twitter paid API dependence;
- manually curated “smart wallets” that leak future information.
