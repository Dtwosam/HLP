# HLP External Source Register

Verified: 2026-09-04

External services can change. Reverify a source before implementing a dependency whose limits or contract addresses matter.

## SRC-001 — Robinhood Chain Connecting
URL: https://docs.robinhood.com/chain/connecting/

Supports:
- chain ID 4663;
- official public RPC/sequencer endpoints;
- Alchemy recommendation;
- public endpoint rate-limit warning.

## SRC-002 — Robinhood Chain Token Contracts
URL: https://docs.robinhood.com/chain/contracts/

Supports:
- canonical WETH identity;
- canonical USDG identity;
- canonical Stock Token address registry.

## SRC-003 — Robinhood Stock Token APIs
URL: https://docs.robinhood.com/chain/stock-token-apis/

Supports:
- /assets address registry by chain;
- read-only metadata/price endpoints;
- current 60 req/s limit;
- deterministic Stock Token exclusions.

Do not use ticker alone for identity.

## SRC-004 — Pons official contracts
URL: https://github.com/ponsdotdev/ponsfamily

Verified current repository state:
- V1 PonsLaunchFactory: 0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB
- V2 PonsV2LaunchFactory: 0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e
- V1 source exposes launch/deployment events.
- V2 source exposes TokenLaunched/PoolGraduated plus CurveBuy/CurveSell events.

Allowed use:
protocol-specific launch/trade/graduation adapter.

Rule:
verify deployed code/start blocks before freezing an ingestion adapter.

## SRC-005 — Alchemy pricing and Robinhood API
URLs:
https://www.alchemy.com/pricing
https://www.alchemy.com/docs/reference/pricing-plans
https://www.alchemy.com/docs/chains/robinhood-chain/robinhood-chain-api-endpoints/eth-get-logs

Verified:
- Free: 30M CU/month;
- full archive data;
- Token/Transfers/WebSocket availability;
- Robinhood Free eth_getLogs range: 10 blocks/query;
- eth_getLogs cost: 60 CU.

Allowed use:
targeted archive/state, enrichment, live WebSocket, fallback.

Not allowed as the assumed full-history crawler without a new proven method.

## SRC-006 — The Graph / Substreams Robinhood
URLs:
https://thegraph.com/docs/en/supported-networks/robinhood/
https://thegraph.market/
https://thegraph.com/docs/en/substreams/

Verified:
- Robinhood eip155:4663 supported;
- Substreams/Firehose available;
- Free plan currently advertises 7M blocks and 5 GiB egress, no credit card required;
- reusable packages can be consumed directly.

Allowed use:
primary candidate bulk/backfill and live canonical event stream.

Constraint:
Phase 1 must measure whether required complete history fits free quotas.

## SRC-007 — Robinhood Uniswap V4 Substreams package
URL: https://substreams.dev/packages/uniswap-v4-robinhood/latest

Verified:
- package ref uniswap-v4-robinhood@v0.1.2 at verification date;
- complete unfiltered V4 event module;
- points to a broader Uniswap-published Robinhood v2/v3/v4 tape;
- supports Robinhood endpoint alias.

Allowed use:
bootstrap/reference for Uniswap adapter and pricing validation.

Do not treat community enrichment labels as canonical without verification.

## SRC-008 — Supabase pricing
URL: https://supabase.com/pricing

Verified Free limits include:
- 500 MB database/project;
- 1 GB file storage;
- 5 GB egress;
- unlimited API requests;
- inactivity pausing.

Allowed use:
optional compact live operational state.

Not allowed:
full raw historical tape as a design assumption.

## Source priority

1. verified on-chain facts / official contract source;
2. official Robinhood/Uniswap/protocol docs;
3. reproducible open-source Substreams/indexers;
4. explorer/indexer cross-checks;
5. third-party market-data displays.

No source overrides the point-in-time or $0 rules.
