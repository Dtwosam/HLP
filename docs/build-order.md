# HLP Build Order

Status: BASELINE v0.1
Rule: do not skip a phase acceptance gate because a later component is more interesting.

## Phase 0 — Source of Truth & Free-Data Viability

Goal: freeze the problem, anti-leakage rules, outcome semantics and $0 source hierarchy.

Deliverables:
- master specification;
- working contract;
- data-source audit;
- research standard;
- decision log;
- project state;
- build order.

Acceptance:
- scope is Robinhood Chain only;
- $100k universe rule is explicit;
- 5x is documented as minimum outcome, not cap;
- continuous max multiple is retained;
- no predictive criteria are assumed;
- live-learning/champion-challenger rule is frozen;
- free-source risks are explicit.

Checkpoint: hlp-v1-phase0-source-of-truth

## Phase 1 — Historical/Live Data Acquisition Spike

Goal: prove we can reconstruct the information needed for the study at $0 before building a giant dataset.

Tasks:
1. Scaffold Python project, configuration, typed canonical event records and tests.
2. Pin verified Robinhood Chain network/system addresses.
3. Build source probes for:
   - The Graph Market/Substreams on Robinhood;
   - existing Uniswap Robinhood packages where reusable;
   - custom Pons V1/V2 events;
   - Alchemy free archive/WebSocket;
   - Robinhood public RPC;
   - Blockscout verification;
   - DEX Screener/GeckoTerminal only as cross-checks.
4. Find first relevant blocks for Pons V1, Pons V2 and material Uniswap deployments.
5. Backfill a bounded but representative window containing:
   - launches;
   - bonding-curve trades;
   - V3/V4 swaps;
   - liquidity/graduation events;
   - ERC-20 transfers;
   - known large runners and failed coins.
6. Measure requests, processed blocks, egress, runtime and free-tier consumption.
7. Reconstruct at least 10–20 tokens end-to-end and compare with explorer/DEX views.

Acceptance:
- launch -> trades -> price -> transfers -> holder state can be reproduced;
- no unexplained event gaps in the validation window;
- protocol amounts/prices reconcile within documented tolerance;
- source usage is measured, not guessed;
- a credible full-history plan fits $0 OR a different free path is identified and proven;
- if full-history acquisition cannot fit $0, Phase 1 is BLOCKED and later modeling does not begin.

Checkpoint: hlp-v1-phase1-data-viability

## Phase 2 — Chain-Wide Universe & Outcome Dataset

Goal: produce the unbiased population of eligible coins and their lifecycle outcomes.

Tasks:
1. Enumerate material launch/trading sources across Robinhood Chain.
2. Build deterministic exclusion registry for WETH, USDG, Robinhood Stock Tokens/ETFs and system assets.
3. Reconstruct token supply and USD price histories.
4. Compute market-cap proxy and identify every token that ever crossed $100k in the covered history.
5. Quantify coverage by venue, launch source and observed volume.
6. Empirically develop the first-major-dump detector using only price-path structure—not predictive wallet/holder features.
7. Freeze dump-detector version.
8. Compute outcome labels:
   - max_post_dump_multiple;
   - >=5x minimum label;
   - milestone times;
   - later highs;
   - path/drawdown statistics.

Acceptance:
- universe can be regenerated from raw data;
- eligibility/exclusion is address-based and deterministic;
- every included token has provenance;
- dump detector is deterministic and has point-in-time live semantics;
- no future outcome information is present in feature inputs.

Checkpoint: hlp-v1-phase2-universe-labels

## Phase 3 — Point-in-Time Feature Store

Goal: create broad candidate measurements without deciding in advance which one is “the signal.”

Feature families may include:
- price/drawdown;
- trade flow;
- unique and repeat participants;
- holder state;
- concentration/redistribution;
- creator/early-wallet activity;
- funding/relationship graph;
- liquidity/depth;
- price impact/absorption;
- cohort retention;
- venue/launch mechanics;
- chain-wide regime.

Tasks:
1. Define feature snapshot times relative to observable dump states.
2. Implement all features point-in-time.
3. Add leakage tests for wallet labels and historical balances.
4. Version features and provenance.
5. Record missingness/data-quality flags rather than silently imputing everything.

Acceptance:
- each feature has a formula and timestamp semantics;
- replaying a historical block cannot see future state;
- feature generation is deterministic;
- matched failed coins have the same feature coverage as winners.

Checkpoint: hlp-v1-phase3-feature-store

## Phase 4 — Signal Discovery

Goal: discover what actually separates comeback runners from failures.

Tasks:
- base-rate analysis;
- matched winner/failure comparisons;
- univariate effect sizes and distributions;
- nonlinear relationships;
- feature interactions;
- simple decision trees/logistic models;
- permutation/stability checks;
- repeated-sampling/multiple-testing controls;
- cluster/sequence analysis where useful;
- examine whether 10x/20x+ runners have distinct patterns from ordinary >=5x winners.

Acceptance:
- findings report both winner frequency and failure frequency;
- no “signal” is promoted from winner-only anecdotes;
- each candidate relationship survives at least one unseen chronological slice;
- rejected hypotheses remain logged.

Checkpoint: hlp-v1-phase4-discovery

## Phase 5 — Baseline Comeback Model

Goal: convert validated relationships into a calibrated rank/score.

Tasks:
1. Freeze chronological train/validation/final-test windows.
2. Train transparent baselines first.
3. Add boosted/tree models only if they materially improve unseen performance.
4. Model both >=5x probability and continuous max multiple/ranking.
5. Calibrate probabilities.
6. Select signal threshold from validation utility/precision, never final test.

Acceptance:
- positive unseen separation from base rate;
- calibration is acceptable;
- results are not driven by one launchpad/month;
- complex model must beat simple baseline enough to justify complexity.

Checkpoint: hlp-v1-phase5-model

## Phase 6 — Historical Live-Replay / Signal Timing

Goal: answer “what would HLP actually have told us at the time?”

Tasks:
- event-by-event or block-aware replay;
- emit NO SIGNAL / WATCH / SIGNAL states using only then-known data;
- measure exact signal timestamp/market cap;
- record post-signal 2x/3x/5x/10x+ outcomes;
- measure maximum adverse excursion and time-to-target;
- model realistic DEX slippage/price impact for interpretation, even though V1 does not execute.

Acceptance:
- no historical signal is backdated to the bottom;
- final-test replay remains viable;
- false-positive burden is acceptable for the desired scarce-signal behavior.

Checkpoint: hlp-v1-phase6-replay

## Phase 7 — Live Shadow Scanner

Goal: run the frozen model on Robinhood Chain with no order capability.

Components:
- live chain stream;
- token/universe tracker;
- dump-state machine;
- incremental feature engine;
- model scorer;
- signal ledger;
- explanation/reason codes;
- data-health monitor;
- restart/cursor recovery.

Acceptance:
- scanner survives disconnect/restart without missing/double-counting;
- live features match offline replay on the same blocks;
- signals are timestamped before outcomes;
- there is structurally no wallet/private-key/order path.

Checkpoint: hlp-v1-phase7-shadow

## Phase 8 — Continuous Learning

Goal: let new Robinhood coins improve the system without letting recent noise corrupt it.

Tasks:
- append immutable live observations;
- mature labels after sufficient observation;
- detect data/regime drift;
- retrain after a frozen sample-count/time gate;
- create challenger model;
- evaluate on forward-only windows;
- promote only if challenger beats champion under frozen criteria;
- keep rollback/model registry.

Acceptance:
- every production model can be reproduced;
- automatic retraining cannot automatically promote a worse model;
- old predictions remain tied to their original model version.

Checkpoint: hlp-v1-phase8-learning

## Phase 9 — Signal Delivery & Monitoring

Goal: make the signal useful to a human operator.

Initial surfaces:
- CLI;
- compact web dashboard if justified;
- optional Telegram/Discord notification only if a free reliable path exists.

Show:
- score/probability;
- token/address;
- current market-cap proxy;
- why it triggered;
- model/data version;
- historical comparable setup stats;
- invalidation/data-quality warnings;
- post-signal tracking.

Acceptance:
- delivery latency and reliability measured;
- UI cannot imply certainty or guaranteed returns;
- same underlying signal ledger feeds every surface.

Checkpoint: hlp-v1-phase9-product

## Phase 10 — Production Hardening

Goal: long-running reliability at $0.

Tasks:
- bounded storage/retention;
- cursor checkpoints;
- health checks;
- rate-limit budgeting;
- backup/export;
- deterministic rebuild path;
- provider fallback tests;
- security review.

Acceptance:
- system can be rebuilt from canonical data + versioned code;
- no paid overage is enabled;
- provider outage does not silently fabricate or duplicate signals.

## Future execution

Automatic trading is not part of V1. It requires a separate approved scope, risk model, wallet security design and forward signal evidence.
