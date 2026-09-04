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

What Phase 1 has established so far:
- Robinhood public RPC is live and usable for current/bounded reads, but it is pruned for older state;
- both official Pons V1/V2 factory bytecodes are present on mainnet;
- Alchemy Free cannot efficiently crawl all Robinhood logs because its Robinhood eth_getLogs range is capped at 10 blocks;
- hoodexplorer documents a keyless indexed-log/archive API that could avoid scanning every block, but GitHub-hosted runners currently cannot route to that service;
- The Graph/Substreams remains the other leading bulk path, with finite free processed-block/egress quotas.

Phase 1 must prove at least one complete-enough historical path from a reachable runtime and measure it before dataset construction.

## Current Phase 1 progress

- [x] Python package/test scaffold
- [x] canonical Robinhood RPC client with wrong-chain guard
- [x] immutable raw-log / Pons launch / curve-trade record types
- [x] verified Pons V1/V2 factory addresses and source event signatures
- [x] Pons V1/V2 launch decoders
- [x] Pons V2 CurveBuy/CurveSell decoders
- [x] public-RPC live smoke: chain 4663, both factory bytecodes, bounded logs
- [x] public-RPC archive limitation reproduced and documented
- [x] hoodexplorer client, rate-aware pagination and immutable snapshot manifest writer
- [x] reproducible hood-pons-sample CLI
- [x] required CI unit tests green during Phase 1 iterations
- [ ] validate hoodexplorer sampler from a network that can reach it
- [ ] benchmark Substreams/reusable Uniswap package path
- [ ] build/validate Uniswap event adapter
- [ ] reconstruct representative Pons tokens end-to-end
- [ ] measure full-history request/block/egress projection
- [ ] Phase 1 PASS/BLOCK decision

## Deferred decisions

- exact first-major-dump algorithm;
- exact USD pricing route;
- exact chronological split dates;
- exact feature list;
- exact model family;
- exact signal threshold;
- exact live UI/notification surface;
- any future execution/trading integration.
