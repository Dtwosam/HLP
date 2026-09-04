# HLP Free Data & Infrastructure Audit

Verified: 2026-09-04
Requirement: canonical V1 must remain $0.

Status summary: BUILDABLE, with one Phase-1 viability gate still open — full historical bulk acquisition at $0 must be measured on the real Robinhood dataset.

## 1. Robinhood Chain official endpoints — PASS for verification/fallback

Official documentation:
https://docs.robinhood.com/chain/connecting/

Verified:
- mainnet chain ID 4663;
- ETH native gas;
- public RPC: https://rpc.mainnet.chain.robinhood.com;
- public sequencer feed: wss://feed.mainnet.chain.robinhood.com;
- Blockscout explorer is public;
- Robinhood recommends Alchemy for application infrastructure.

Use:
- chain identity;
- targeted state verification;
- fallback reads;
- sequencer/live experimentation.

Constraint:
- Robinhood explicitly calls public endpoints rate-limited and not recommended for production. Do not plan a full historical crawl against them without a measured spike.

## 2. Alchemy Free — PASS for targeted archive/live, FAIL as sole bulk-history crawler

Docs:
https://www.alchemy.com/pricing
https://www.alchemy.com/docs/reference/pricing-plans
https://www.alchemy.com/docs/chains/robinhood-chain/robinhood-chain-api-endpoints/eth-get-logs

Current free allowance:
- 30M compute units/month;
- full archive data;
- Node API;
- Token API;
- Transfers API;
- Smart WebSockets;
- free-tier throughput limits.

Critical Robinhood constraint:
- eth_getLogs on the Free plan is limited to a 10-block range per request;
- each eth_getLogs request costs 60 compute units.

Conclusion:
Alchemy is excellent for targeted historical state, wallet/transfer enrichment, archive calls and live WebSockets. It is not the canonical full-history log crawler for HLP.

## 3. The Graph Market / Substreams / Firehose — PRIMARY BULK-HISTORY CANDIDATE, SPIKE REQUIRED

Docs:
https://thegraph.market/
https://thegraph.com/docs/en/supported-networks/robinhood/
https://thegraph.com/docs/en/substreams/

Verified:
- Robinhood Chain (eip155:4663) is supported;
- Substreams/Firehose can process archival chain data and stream live;
- existing packages can be reused/composed;
- current Free plan advertises 7M processed blocks and 5 GiB egress with no credit card required.

Useful current package:
https://substreams.dev/packages/uniswap-v4-robinhood/latest

That package exposes an unfiltered Robinhood Uniswap V4 event tape and notes a broader Uniswap v2/v3/v4 Robinhood package published by Uniswap.

Risk:
Robinhood Chain produces blocks very quickly and its history is already far larger than 7M blocks. A naive genesis-to-head custom pass may exceed the monthly free block allowance.

Phase-1 question:
Can cached/reusable protocol Substreams, protocol deployment start blocks, targeted modules and/or the Token API reconstruct the required Pons + Uniswap history within the free quota?

Do not declare this solved until measured.

## 3A. hoodexplorer — PROMISING KEYLESS ARCHIVE/INDEX CANDIDATE, HOST NETWORK CAVEAT

Docs:
https://www.hoodexplorer.org/apidocs

Verified documentation:
- Etherscan-compatible read API;
- keyless access at 60 requests/minute per IP;
- paginated list endpoints with up to 1,000 rows/page;
- event-log filtering by address and/or topic0 across indexed history;
- contract-creation lookup;
- ERC-20 transfer endpoints;
- token holder list/count endpoints for current state;
- Proxy module backed by hoodexplorer's own archive node for read-only eth_* methods.

Why this matters:
HLP can potentially request only Pons/Uniswap event families instead of processing every Robinhood block, making the historical study dramatically cheaper in free-quota terms.

Current caveat:
GitHub-hosted Actions runners tested on 2026-09-04 could not route to hoodexplorer over IPv4 or normal Python HTTPS, while the public website/API documentation remained accessible from other networks. Therefore hoodexplorer is not a required CI dependency. Phase 1 must validate the historical sampler from a reachable runtime before promoting it to canonical bulk acquisition.

Use:
- historical Pons launch/trade event candidate;
- archive state reads;
- contract creation metadata;
- bounded cross-checks and potential bulk extraction.

Do not use near-live holder-count/list endpoints as historical point-in-time holder truth. Historical holder states must be reconstructed from Transfer events.

## 4. Pons contracts — PASS, open source and directly decodable

Official source:
https://github.com/ponsdotdev/ponsfamily

Current official repository identifies:
- V1 PonsLaunchFactory: 0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB
- V2 PonsV2LaunchFactory: 0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e

V1 emits deployment/launch events and starts in Uniswap V3.
V2 emits TokenLaunched/PoolGraduated and uses a per-token bonding curve whose CurveBuy/CurveSell events make pre-graduation trades directly reconstructable before it graduates to Uniswap V4.

Use:
- protocol adapter;
- launch discovery;
- creator/deployer identity;
- exact curve trade reconstruction;
- graduation transition.

Rule:
Addresses/event ABIs are versioned. Before ingestion, verify deployed bytecode/events against current source and record deployment start blocks.

Pons is not the entire HLP universe.

## 5. Uniswap on Robinhood Chain — PASS as core DEX source

Robinhood ecosystem documentation identifies Uniswap as the public DEX.

The Graph registry already contains Robinhood Uniswap packages. HLP should reuse maintained packages when possible rather than decode every DEX event from scratch.

Use:
- V2/V3/V4 pool creation;
- swaps;
- liquidity;
- post-graduation price discovery;
- quote routing.

Exact deployment addresses/start blocks must be frozen during Phase 1 from official/verified sources.

## 6. Robinhood canonical asset registry — PASS

Docs:
https://docs.robinhood.com/chain/contracts/
https://docs.robinhood.com/chain/stock-token-apis/

Verified:
- canonical WETH address is documented;
- canonical USDG address is documented;
- /rhj/assets provides Stock Token deployment addresses by chain;
- API rate limit is 60 requests/second.

Use:
- deterministic exclusion registry;
- prevent ticker impersonators from being mistaken for canonical Stock Tokens;
- quote-asset identity/enrichment.

Do not classify by token symbol.

## 7. Blockscout — PASS as explorer/verification/fallback

Robinhood’s official explorer is Blockscout.

Use:
- deployment/contract verification;
- transaction/log spot checks;
- source-code verification;
- bounded fallback discovery.

Do not make Blockscout the only canonical high-frequency/live ingestion path.

## 8. DEX Screener / GeckoTerminal — PASS for cross-check/current discovery, not canonical history

Use:
- sanity-check token/pool addresses;
- compare current price/liquidity/market-cap displays;
- discover missed venues during coverage audits.

Do not use third-party marketCap, holder or trend labels as ground truth where HLP can reconstruct the underlying facts.

Historical completeness and free retention are not strong enough to make these the canonical research tape.

## 9. USD pricing — VIABLE, exact route to freeze in Phase 1

Canonical WETH and USDG exist on Robinhood Chain and Uniswap liquidity can anchor token-to-USD pricing.

For canonical Stock Token quote assets, Robinhood documents per-token on-chain Chainlink pricing and a read-only Stock Token price API.

Phase 1 must validate:
- quote direction/decimals;
- native ETH vs WETH handling;
- stable/native pool quality;
- multi-hop rules;
- timestamp/block semantics.

## 10. Bulk research storage — PASS locally

Use:
- Parquet for immutable/partitioned facts;
- DuckDB for analytical joins;
- optional Polars/Pandas for transforms.

Cost: $0.

Reason:
raw swaps/transfers can be too large for a free hosted database. Keep the bulk historical tape local/rebuildable.

## 11. Supabase Free — OPTIONAL PASS for compact live state, not bulk raw history

Pricing:
https://supabase.com/pricing

Current Free plan includes:
- 500 MB database per project;
- 1 GB file storage;
- 5 GB egress;
- unlimited API requests;
- projects may pause after inactivity.

Use only if/when needed for compact:
- token registry;
- current live state;
- signal ledger;
- model registry metadata;
- outcome summaries.

Do not put the full raw historical event tape in Supabase Free.

A separate HLP project should be used rather than mixing with unrelated projects. Project creation is deferred until the phase that needs it.

## 12. GitHub / GitHub Actions — PASS

The HLP repository is public.

Use:
- source control;
- unit/integration CI;
- deterministic research jobs that fit runner limits;
- scheduled model evaluation/retraining where appropriate.

Do not use ephemeral GitHub Actions as the sole always-on low-latency live daemon.

## 13. Modeling libraries — PASS

Free/open-source Python stack is sufficient:
- NumPy;
- Polars/Pandas;
- DuckDB;
- scikit-learn;
- optional LightGBM/XGBoost;
- matplotlib/Plotly for research visualization.

No paid AI/model API is required.

## 14. Social data — NOT A V1 DEPENDENCY

A reliable historical X/Twitter firehose is not assumed to be free.

Therefore social engagement is not part of the canonical V1 feature set unless a reproducible zero-cost point-in-time source is later proven.

This is not a blocker: HLP’s primary hypothesis concerns on-chain behavior.

## 15. Free-stack verdict

Available now:
- chain access: yes;
- live streaming: yes;
- Pons source/ABIs: yes;
- Uniswap data path: yes;
- token/transfer/state enrichment: yes;
- canonical non-memecoin registry: yes;
- local historical storage: yes;
- modeling: yes;
- CI: yes;
- optional compact hosted state: yes.

Not yet proven:
- complete historical Pons + chain-wide DEX reconstruction within free bulk-indexing quotas.

That uncertainty is exactly what Phase 1 must settle before Phase 2.
