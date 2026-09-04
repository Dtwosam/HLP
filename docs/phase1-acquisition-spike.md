# Phase 1 — Historical/Live Data Acquisition Spike

Status: ACTIVE
Started: 2026-09-04

## Purpose

Prove the minimum canonical acquisition path before bulk collection.

This phase is not allowed to invent alpha features or train a comeback model.

## Spike A — direct Robinhood RPC

Acceptance:
- eth_chainId == 4663;
- current head can be read;
- Pons V1 factory has deployed code;
- Pons V2 factory has deployed code;
- bounded eth_getLogs works;
- the client fails closed on wrong chain/malformed RPC.

Implementation:
- src/hlp/data/rpc.py
- src/hlp/protocols/pons.py
- hlp network-smoke
- hlp pons-scan

## Spike B — locate protocol deployment/start blocks

Find exact first event/code blocks for:
- Pons V1 factory;
- Pons V2 factory;
- relevant Uniswap V3/V4 deployments.

Use binary search on eth_getCode and bounded event verification where practical.

Record source and block/timestamp.

## Spike C — representative end-to-end reconstruction

Select:
- >=5 known/likely comeback runners;
- >=5 failures;
- both Pons generations where possible;
- pre/post graduation paths.

Reconstruct:
launch -> curve/DEX trades -> transfer/holder changes -> price -> market-cap proxy.

No research conclusions are allowed from this tiny sample. It is an ingestion validation sample only.

## Spike D — bulk free-path benchmark

Primary candidate: The Graph Market / Substreams.

Measure:
- processed blocks;
- bytes/egress;
- wall-clock time;
- output event count;
- reusable/cached package behavior;
- whether only protocol-relevant blocks/modules can be processed;
- projected full-history use.

Fallback/complement:
- Alchemy free archive/Transfers/Token APIs for targeted enrichment;
- direct public RPC for verification;
- Blockscout for verification.

## PASS

Phase 1 passes only if a reproducible complete-enough historical path can be operated at $0 and the representative sample reconciles against independent explorer/DEX evidence.

If not, Phase 1 is BLOCKED and the ingestion architecture is redesigned before any feature/model work.
