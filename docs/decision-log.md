# HLP Decision Log

## DEC-001 — Robinhood Chain only
Date: 2026-09-04
Status: ACCEPTED

V1 studies Robinhood Chain mainnet only. Cross-chain support is outside the current scope.

## DEC-002 — $100k universe entry
Date: 2026-09-04
Status: ACCEPTED

An eligible speculative token enters the research universe if it reached at least $100,000 market-cap proxy at any point in the covered history.

The canonical proxy is reconstructed from point-in-time token price and total supply, with third-party displays used only for validation.

## DEC-003 — 5x is minimum comeback, not target
Date: 2026-09-04
Status: ACCEPTED

A positive comeback must later offer at least 5x after the first major dump.

The full maximum post-dump multiple is retained. HLP must distinguish ordinary >=5x recoveries from 10x/20x/50x+ outcomes.

## DEC-004 — predictive criteria are discovered, not assumed
Date: 2026-09-04
Status: ACCEPTED

No holder, sniper, wallet, volume, liquidity, chart or social pattern is treated as a required success condition in advance.

Candidate measurements may be created broadly, but their usefulness must be demonstrated against failures on unseen time periods.

## DEC-005 — first-major-dump threshold is not preselected
Date: 2026-09-04
Status: ACCEPTED

Phase 0 does not define “major dump” as an arbitrary fixed percentage/time.

Phase 2 develops a deterministic point-in-time-compatible detector from actual price paths and freezes it before predictive experiments.

## DEC-006 — on-chain facts are canonical
Date: 2026-09-04
Status: ACCEPTED

Raw Robinhood Chain events/state are source of truth where reconstructable.

Third-party APIs may accelerate discovery and validation but opaque labels cannot silently become canonical research targets.

## DEC-007 — $0 hard constraint
Date: 2026-09-04
Status: ACCEPTED

No paid data, paid AI model, paid database or paid hosting is required for V1.

Free-tier limits are measured. HLP does not silently upgrade or enable overage.

## DEC-008 — chain-wide, not Pons-only
Date: 2026-09-04
Status: ACCEPTED

Pons is a major adapter and clean launch source, but HLP’s universe is Robinhood Chain-wide.

Material launch/DEX venues must be measured and covered or explicitly flagged as a coverage gap.

## DEC-009 — controlled continuous learning
Date: 2026-09-04
Status: ACCEPTED

Live coins remain tracked through their outcomes and join later training cohorts.

Production models do not self-modify after each coin. Challenger models are retrained in controlled batches and replace the champion only after frozen forward evaluation.

## DEC-010 — signal-only V1
Date: 2026-09-04
Status: ACCEPTED

V1 can emit WATCH/SIGNAL/NO SIGNAL states and track post-signal outcomes.

It contains no wallet signing or automatic trade execution. Any execution scope requires a future explicit amendment.

## DEC-011 — bulk historical path must prove $0 viability first
Date: 2026-09-04
Status: ACCEPTED

Alchemy Free is not used as the sole historical log crawler because Robinhood eth_getLogs is capped to 10 blocks/query on that tier.

Substreams/Firehose and existing protocol packages are the primary candidate, but full-history feasibility is an explicit Phase 1 acceptance gate because free processed-block/egress quotas are finite.
