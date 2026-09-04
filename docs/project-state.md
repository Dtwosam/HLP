# HLP Project State

Updated: 2026-09-04
Repository: Dtwosam/HLP
Current phase: Phase 0 — Source of Truth & Free-Data Viability
Status: IN PROGRESS
Next phase: Phase 1 — Historical/Live Data Acquisition Spike

## Frozen user requirements

- Robinhood Chain only.
- Study every eligible speculative/memecoin token that reaches at least $100,000 market-cap proxy at any point.
- The only precommitted positive threshold is >=5x after the first major dump.
- 5x is the minimum, not the target/cap.
- Preserve full upside magnitude so 10x/20x/50x+ runners teach the model more than a binary label.
- Do not pre-assume what holder/wallet/volume/liquidity signal matters.
- Derive predictive patterns from the studied population.
- End product is a live buy-signal/ranking tool.
- Live coins continue becoming training data.
- Model updates are controlled, validated and versioned.
- User expects HLP to be built end to end in this repository.
- Development/data/infrastructure must remain $0.

## Phase 0 completed

- [x] correct repository confirmed
- [x] repository inspected: clean baseline
- [x] official Robinhood network/access sources verified
- [x] current official Pons source repository inspected
- [x] Pons V1/V2 factory generations/events identified
- [x] Alchemy free-tier capabilities/eth_getLogs limitation verified
- [x] The Graph/Substreams Robinhood support/free allowance verified
- [x] Robinhood canonical Stock Token registry/API verified
- [x] local/hosted storage options reviewed
- [x] source-of-truth documents drafted on phase0/source-of-truth

## Phase 0 remaining gate

- [ ] review source-of-truth PR
- [ ] record Phase 0 PASS/checkpoint after merge

## Known viability risk

Full historical bulk ingestion is not yet proven at $0.

Alchemy Free cannot efficiently crawl all Robinhood logs because free eth_getLogs queries are capped at 10 blocks.

The Graph/Substreams is the leading bulk path, but the current free plan includes 7M processed blocks / 5 GiB egress while Robinhood Chain history is larger. Existing cached Uniswap packages and protocol-specific start blocks may make the required dataset practical; Phase 1 must measure this.

This is not a modeling problem and must be resolved before dataset construction.

## Immediate next action after Phase 0

Build the Phase 1 acquisition spike:
1. Python project scaffold + tests.
2. Reusable Substreams package discovery.
3. Pons V1/V2 adapters.
4. Uniswap adapter/tape.
5. bounded historical sample.
6. cross-check with explorer/DEX views.
7. quota/cost projection.
8. PASS/BLOCK decision for full history.

## Deferred decisions

- exact first-major-dump algorithm;
- exact USD pricing route;
- exact chronological split dates;
- exact feature list;
- exact model family;
- exact signal threshold;
- exact live UI/notification surface;
- any future execution/trading integration.
