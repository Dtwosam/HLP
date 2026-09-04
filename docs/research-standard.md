# HLP Research & Testing Standard

## 1. Why this exists

The easiest way to “find” a memecoin comeback signal is to look only at famous winners and explain them afterward.

HLP must do the opposite: construct the population first, freeze time semantics, compare winners with failures, and then ask what truly separates them.

## 2. Population before patterns

Do not hand-pick winner examples as the primary dataset.

First build the eligible universe: every covered Robinhood Chain speculative token that reached at least $100k market-cap proxy.

Only after the universe is frozen may outcome groups be compared.

## 3. Outcome target

Binary minimum:
- comeback_5x = true when post-first-major-dump opportunity reaches >=5x.

Continuous:
- max_post_dump_multiple remains the primary magnitude outcome.

Also retain milestone/time/path targets.

Do not collapse 5x and 50x into identical research records.

## 4. Dump detector separation

The first-major-dump detector is a lifecycle/event-detection problem, not the predictive alpha model.

Develop it from price-path behavior, validate it for live detectability, then freeze it.

Do not tune its thresholds to maximize later model returns.

## 5. Point-in-time snapshots

For each coin, features must be generated only from blocks at or before the candidate decision timestamp.

Historical replay must be able to reproduce the same values.

If a value can only be known after the future rally, it is a label or analysis artifact, not a feature.

## 6. Wallet-label leakage

“Smart money” is especially dangerous.

A wallet may only receive a historical performance feature based on trades completed before the target coin’s decision timestamp.

Never call a wallet smart in July because it became profitable in August.

Prefer raw measurable wallet histories over opaque current third-party labels.

## 7. Comparators

At minimum compare:
- >=5x comeback coins;
- eligible coins with a similar lifecycle/dump state that never hit 5x.

Matching/stratification candidates may include time period, pre-dump market-cap band, launch source and liquidity regime so the model does not merely learn that one month or one launchpad was hot.

Matching variables themselves must not encode the future.

## 8. Data splits

Final evaluation is chronological.

Recommended shape after dataset inspection:
- discovery/train period;
- validation period;
- untouched final test period;
- later rolling walk-forward windows.

Exact dates are frozen only after Phase 2 coverage is known.

No random shuffle may substitute for final time-aware evaluation.

## 9. Feature discovery

Allowed:
- broad feature generation;
- effect-size analysis;
- stable nonlinear transforms;
- interaction tests;
- transparent baselines;
- unsupervised sequence/cluster exploration.

Required safeguards:
- log every serious experiment;
- measure how often a proposed signal also appears in failures;
- use bootstrap/time-slice stability where practical;
- correct expectations for repeated hypothesis testing;
- do not repeatedly peek at final test results.

## 10. Model hierarchy

Start with:
1. base rate;
2. simple thresholds learned on training data;
3. logistic/regularized linear models;
4. shallow trees/ensembles;
5. boosted models if justified.

Deep learning is not a default.

Complexity must materially improve unseen behavior, calibration or ranking stability.

## 11. Metrics

Classification/ranking:
- precision;
- recall/coverage;
- PR-AUC;
- ROC-AUC only as secondary when class imbalance is high;
- Brier/log loss;
- calibration curve;
- lift over base rate;
- precision at top-k/top-percentile.

Trading-relevance:
- 2x/3x/5x/10x+ hit rates after signal;
- max_post_signal_multiple;
- maximum adverse excursion;
- time to milestone;
- time to failure;
- signal frequency;
- performance by month/regime/source/market-cap band.

A high AUC with unusable top-signal precision is not enough.

## 12. Signal threshold

The production threshold is selected on validation data according to a frozen objective emphasizing scarce, high-quality signals.

The system is allowed to remain silent.

Do not optimize threshold on the untouched final test set.

## 13. Historical replay

For every emitted historical signal record:
- exact block/time;
- then-known price and market-cap proxy;
- model/feature versions;
- confidence/score;
- reason features;
- subsequent outcome.

Do not move the signal backward to the eventual bottom.

## 14. Continuous-learning gate

Live outcomes are appended to a new cohort.

Retraining trigger must be frozen by time or minimum new sample count.

A challenger is evaluated on forward data unavailable to the current champion’s fit.

Promotion requires documented improvement and no unacceptable degradation in false positives/calibration/coverage.

If the challenger loses, keep the champion and keep the failed experiment.

## 15. Reproducibility record

Every experiment stores:
- experiment ID;
- git SHA;
- data cutoff/manifest;
- universe/dump/label/feature versions;
- split;
- model params;
- seed;
- metrics;
- artifact/checksum;
- conclusion.

## 16. Claims

Never write “HLP predicts 5x coins” based on in-sample results.

Acceptable claim language must state the evaluation period, sample size, base rate and forward/out-of-sample evidence.

No guarantee language.
