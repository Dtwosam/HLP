# HLP

HLP is a HYPE-focused Hyperliquid mainnet research and, later, autonomous execution system.

The implementation contract is [SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md). Read that before changing architecture or data contracts.

## Current phase

**Phase 1: read-only mainnet recorder.**

There is no wallet key, signing code, order placement, leverage management, or transfer functionality in this phase.

The recorder subscribes to first-party Hyperliquid mainnet WebSocket feeds and stores the original received messages inside append-only event envelopes.

### Deep HYPE feeds

- trades
- l2Book
- bbo
- activeAssetCtx
- 1m candle

### Context feeds

BTC, ETH, and SOL:

- trades
- bbo
- activeAssetCtx
- 1m candle

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
hlp-record
```

Optional data directory:

```bash
HLP_DATA_DIR=/path/to/data hlp-record
```

Default output:

```text
data/raw/mainnet/YYYY-MM-DD/HH/<channel>-<coin>.jsonl.gz
```

The process prints a periodic health object with feed counts, last-message age, reconnect count, queue depth, and write errors.

## Safety boundary

Phase 1 is intentionally public-data-only. Do not add an API wallet/private key until the research, validation, shadow-trading, and risk layers described in the source of truth are in place.
