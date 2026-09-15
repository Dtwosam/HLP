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
- Current V2 meme hook cross-verified from current Robinhood/Pons indexing docs: 0xe5e702641ea86f4ae6cc3cdaed2b886f976be044.
- Current Robinhood Uniswap V4 PoolManager: 0x8366a39CC670B4001A1121B8F6A443A643e40951.

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

## SRC-009 — hoodexplorer Robinhood API
URL: https://www.hoodexplorer.org/apidocs

Verified documentation on 2026-09-04:
- keyless Etherscan-compatible API at 60 requests/min/IP;
- list pagination up to 1,000 rows;
- indexed event logs filtered by address/topic0;
- contract creation and token-transfer endpoints;
- read-only eth_* proxy backed by an archive node.

Allowed use:
historical acquisition candidate and independent verification.

Constraint:
GitHub-hosted runners could not reach the service during Phase 1 networking tests, so this source cannot be a required CI dependency unless that changes. Promote to canonical bulk source only after the sampler is exercised successfully from a reachable runtime and reconciled against independent evidence.


## SRC-010 — NodeFlare Robinhood RPC
URLs:
https://nodeflare.app/chains/robinhood
https://nodeflare.app/chains/robinhood/eth_getlogs

Verified current offer:
- public no-key Robinhood RPC;
- free keyed tier with 2,000,000 CU/month and no credit card;
- eth_getLogs is a keyed heavy method at 25 CU/call;
- current docs describe historical state support.

Phase-1 runtime caveat:
GitHub-hosted shared runners hit HTTP 429 immediately on the public endpoint. Do not use GitHub-hosted CI as the historical acquisition worker.

Allowed use:
candidate free archive/state provider and keyed bulk-log source from a dedicated/reachable runtime.

## SRC-011 — BlockReq Robinhood public RPC
URL:
https://blockreq.com/chains/robinhood

Status: REJECTED for zero-key archive history.

Live Phase-1 response from the published public endpoint stated that only the latest 1,024 blocks are served and registration is required for archive access. Keep only as evidence that provider landing-page claims must be validated against actual RPC behavior.


## SRC-012 — SolidRPC Robinhood archive RPC
URLs:
https://solidrpc.io/docs/chains/robinhood-chain
https://solidrpc.io/docs/pricing
https://solidrpc.io/docs/public-rpc
https://solidrpc.io/blog/eth-getlogs-backfill-without-gaps

Verified on 2026-09-04:
- Robinhood Chain ID 4663 is archive-backed;
- Free account plan is $0, no credit card required;
- Free allowance is 10,000 RPC method calls per UTC day;
- Free sustained rate is 10 calls/s with burst 50;
- each billable JSON-RPC method consumes exactly one response unit;
- keyless public Robinhood endpoint exists at https://rpc.solidrpc.io/public/evm/4663;
- public eth_getLogs is capped at 2,000 inclusive blocks;
- authenticated route removes that public-policy range cap, while practical safe widths remain response-density dependent.

Direct HLP evidence:
- GitHub-hosted runner reached the keyless route successfully;
- archive eth_getCode succeeded for Pons V1 at block 30,000,000;
- historical Pons TokenLaunched logs were returned from block 30,000,000–30,001,999;
- binary archive search found Pons V1 first code at block 8,991,118;
- binary archive search found Pons V2 first code at block 26,841,846.

Allowed use:
preferred Phase-1 zero-cost archive/backfill provider, with the keyless route as a verification/development fallback and a Free authenticated key for sustained adaptive backfills.

Security:
send the key via X-API-Key/environment secret; never commit or print it in endpoint URLs.


## SRC-013 — Robinhood Blockscout APIs
URL:
https://robinhoodchain.blockscout.com/

Documentation supports indexed address/log APIs, but both the Etherscan-compatible API and modern /api/v2 address-log route returned HTTP 403 from HLP's GitHub-hosted acquisition runner on 2026-09-04.

Allowed use:
browser/explorer verification and bounded checks from permitted runtimes.

Not allowed:
required GitHub-hosted historical acquisition dependency unless access behavior changes and is reverified.
