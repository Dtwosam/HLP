# HLP — Robinhood Chain Comeback Signal

HLP is an evidence-first research and live-signal system for Robinhood Chain memecoins.

The system studies every eligible speculative token that reaches at least $100,000 in market-cap proxy, reconstructs its first major dump, and learns which observable conditions distinguish coins that later produce a 5x-or-greater post-dump opportunity from coins that do not.

5x is only the minimum qualifying comeback. HLP preserves the full post-dump outcome so a 6x, 12x, 30x or 100x runner is not reduced to the same label.

The project does not begin with assumptions such as “holders must rise” or “snipers must exit.” Predictive signals must be discovered from data, validated chronologically, and shown to beat matched failures out of sample.

## Hard constraints

- Robinhood Chain mainnet only for V1.
- Universe entry: token reached at least $100,000 market-cap proxy at any point.
- Minimum positive outcome: at least 5x after the first major dump.
- Preserve continuous maximum post-dump multiple, drawdown, timing and path.
- $0 development/data/infrastructure budget.
- On-chain facts are canonical. Third-party labels are enrichment only.
- No look-ahead leakage.
- Live observations become new training data.
- Model updates use champion/challenger validation; no self-rewrite after a single coin.
- V1 emits signals only. Real-money order execution is outside the approved scope.

## Read order

1. AGENTS.md
2. docs/project-state.md
3. docs/master-spec.md
4. docs/build-order.md
5. docs/data-source-audit.md
6. docs/research-standard.md
7. docs/decision-log.md
8. docs/source-register.md

## Current phase

Phase 1 — Historical/Live Data Acquisition Spike.

Phase 0 source-of-truth and free-data viability passed. The current gate is to
finish the complete causal Pons >=$100k universe and prove the required
historical acquisition/reconstruction path remains reproducible at $0 before
Phase 2 dataset construction begins.
