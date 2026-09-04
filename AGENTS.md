# AGENTS.md — HLP Working Contract

This file is mandatory reading before changing HLP.

## 1. Mission

Build a Robinhood Chain memecoin comeback signal system that discovers, validates and continuously re-tests patterns that appear before large post-dump recoveries.

Profitability is a hypothesis. A signal is not accepted because it sounds plausible or because it explains famous winners after the fact.

## 2. Canonical read order

Before modifying code or research decisions, read:

1. docs/project-state.md
2. docs/decision-log.md
3. docs/master-spec.md
4. the active phase in docs/build-order.md
5. docs/research-standard.md
6. docs/data-source-audit.md when touching ingestion

Later decision-log entries override older text only when the source-of-truth files are updated in the same change.

## 3. Scope

V1 is Robinhood Chain mainnet only.

The study universe is permissionless/speculative fungible tokens that reach at least $100,000 market-cap proxy at any point. Canonical Robinhood Stock Tokens, USDG, WETH, LP tokens, protocol/system tokens and other deterministic non-memecoin assets are excluded by an explicit asset registry, never by ticker guessing.

Launchpad is not a universe filter. Pons is important, but HLP is chain-wide.

## 4. Outcome rule

The only precommitted success threshold is:

- after the first major dump, a coin later offers at least a 5x price/market-cap opportunity from the post-dump base/trough.

5x is a minimum, not a target or cap.

Always preserve the full maximum multiple and path after the dump. A 50x runner must remain distinguishable from a 5.1x runner.

The algorithm that identifies a completed “first major dump” must be derived and frozen before predictive-model experiments. Do not invent a fixed 50%, 70% or time-window rule merely because it sounds reasonable.

## 5. Feature neutrality

Do not encode proposed signals as truth.

Holder growth, concentration, repeat buyers, creator behavior, wallet funding, buy/sell imbalance, sell absorption, liquidity, volume, price structure, social data and any other candidate are features to test, not assumptions.

If the data says a favorite idea has no separation from failures, reject it.

## 6. Point-in-time discipline

Every feature used for a historical signal must be reconstructable from information available at that exact block/time.

Forbidden leakage includes:

- using a wallet’s future profitability to label it “smart” in the past;
- using future holder counts;
- using a future ATH to define an entry feature;
- fitting normalization across the final test period;
- selecting a dump bottom with future information and pretending it was known live.

Outcome labels may use the future. Predictive features may not.

## 7. Research discipline

- Use chronological splits.
- Maintain an untouched final test window.
- Use walk-forward simulation for final promotion.
- Record false positives and NO SIGNAL states, not just winners.
- Report precision, recall/coverage, calibration, maximum adverse excursion, time-to-target and forward 2x/3x/5x/10x+ outcomes.
- Compare complex models with simple transparent baselines.
- Correct for repeated feature hunting and multiple comparisons where practical.
- Do not optimize on the final test set.

## 8. Continuous learning

Live data is appended immutably and later labeled.

New data does not immediately change the production model. Retraining happens in controlled batches or after a minimum new-sample gate.

Every candidate model is a challenger. It replaces the champion only after passing the frozen time-aware evaluation gate. Record model version, data cutoff, feature version, code commit and evaluation evidence.

## 9. Data rules

- Raw on-chain events/state are canonical.
- Raw data is immutable once recorded.
- Every derived table has provenance and a schema version.
- UTC is the storage time standard.
- Addresses are normalized consistently.
- Contract/event adapters are versioned by protocol generation.
- Third-party market-cap, holder or “smart money” labels may be used only for cross-checks/enrichment unless independently reproducible.
- Never silently drop malformed or unsupported events; quarantine and count them.

## 10. $0 rule

Development and operation must remain free.

Before adding a provider, verify its current free plan and limits. If projected use exceeds the free allowance, do not enable paid overage. Re-design, cache, self-index, reduce scope of that provider, or mark the phase blocked.

No credit card requirement may become a hidden dependency of the canonical path.

## 11. Phase gates

Work one numbered phase at a time. A later phase may be prototyped only when it helps prove the current gate, and that prototype must not be mistaken for phase completion.

A phase is complete only when its acceptance tests and evidence are recorded in docs/project-state.md.

## 12. Execution safety

V1 is a signal/research product, not an autonomous trading bot.

No private keys, wallet signing, swaps or real-money order submission belong in V1. Any future execution feature requires a new explicit scope amendment after the signal system has real forward evidence.

## 13. Secrets and Git

Never commit API keys, wallet keys, database secrets or auth tokens.

Commit only .env.example-style variable names and setup instructions.

## 14. Reproducibility

Every serious experiment must identify:

- code commit;
- source-data snapshot/cutoff;
- universe version;
- dump-detector version;
- feature version;
- label version;
- split definition;
- model/configuration;
- random seed when applicable;
- metrics and artifact path.

Failed experiments remain part of the record.
