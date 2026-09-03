# HLP Source of Truth

This document is the first implementation contract for HLP. Code must follow it unless this document is deliberately updated first.

## Product scope

HLP is a HYPE-only autonomous trading research and execution system for Hyperliquid mainnet.

- Tradable asset: HYPE perpetual only.
- Context assets: BTC, ETH, and SOL. They are inputs, not tradable outputs.
- Network: Hyperliquid mainnet from day one.
- Phase 1 is read-only. No private key, API wallet, order placement, leverage changes, transfers, or withdrawals.
- The default decision later must be NO TRADE unless a validated setup is active and the risk layer approves it.

## Data source priority

1. Hyperliquid official API/docs.
2. Hyperliquid official Python SDK.
3. Data captured directly from Hyperliquid mainnet.
4. Derived features computed from immutable captured data.
5. Third-party sources only when Hyperliquid does not expose the required information.

Third-party data must never silently override first-party Hyperliquid data.

## Mainnet endpoints

- REST info: https://api.hyperliquid.xyz/info
- WebSocket: wss://api.hyperliquid.xyz/ws

## Phase 1 live feeds

Deep HYPE feeds:
- trades
- l2Book
- bbo
- activeAssetCtx
- candle: 1m

Context feeds for BTC, ETH, SOL:
- trades
- bbo
- activeAssetCtx
- candle: 1m

Higher timeframes are derived from the recorded 1m series so their construction is reproducible.

## Important first-party constraints

- l2Book returns/pushes at most 20 levels per side.
- candleSnapshot exposes only the most recent 5,000 candles.
- WebSocket disconnects can happen; the collector must reconnect automatically.
- WebSockets are preferred for lowest-latency realtime data.
- Current documented IP limits include 10 WebSocket connections, 30 new WebSocket connections/minute, and 1,000 subscriptions.
- The recorder should normally use one WebSocket connection.

## Raw event contract

Every received market message must be persisted before feature calculation.

Required envelope fields:

- schema_version
- network
- source
- channel
- coin
- exchange_time_ms, when supplied by Hyperliquid
- received_time_ns, generated locally at receipt
- connection_id
- sequence_local
- payload, unchanged from the received Hyperliquid message

Raw events are append-only. Derived tables/features may be regenerated; raw events must not be rewritten.

## Data integrity rules

- Store numeric values from wire payloads losslessly before casting for calculations.
- Preserve the original payload.
- Detect duplicate trade identifiers using the first-party trade identity fields.
- Track gaps/reconnects explicitly as system events.
- Never fabricate missing order-book states.
- Record local receive time separately from exchange time.
- On reconnect, resubscribe deterministically and record the reconnect event.
- Reject malformed messages into a quarantine/error stream rather than silently dropping them.

## Phase 1 storage

The first recorder writes hourly, compressed JSONL partitions under:

data/raw/<network>/<YYYY-MM-DD>/<HH>/<channel>-<coin>.jsonl.gz

This is intentionally simple and append-only. A later transform layer will convert raw partitions into Parquet for research/backtesting.

The data directory must be gitignored.

## Phase 1 acceptance criteria

The recorder is ready for the next phase only when it can:

1. Connect to Hyperliquid mainnet.
2. Subscribe to every configured feed.
3. Persist raw messages with the required envelope.
4. Reconnect and resubscribe after a forced disconnect.
5. Shut down cleanly without corrupting the current partition.
6. Run without any signing key or trading permission.
7. Produce a health summary with message counts, last-message time by feed, reconnect count, and write errors.

## Execution boundary

No module in Phase 1 may import or instantiate Hyperliquid trading/exchange functionality.

When execution is introduced later:
strategy -> risk engine -> execution engine

A strategy will never be allowed to call the exchange directly.

## Official references

- WebSocket: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket
- WebSocket subscriptions: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions
- Info endpoint: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- Rate limits: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits
- Official Python SDK: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
