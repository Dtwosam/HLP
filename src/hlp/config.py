from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAINNET_WS_URL = "wss://api.hyperliquid.xyz/ws"
NETWORK = "mainnet"

DEEP_COIN = "HYPE"
CONTEXT_COINS = ("BTC", "ETH", "SOL")


def _coin_subscriptions(coin: str, *, deep: bool) -> list[dict[str, Any]]:
    subscriptions: list[dict[str, Any]] = [
        {"type": "trades", "coin": coin},
        {"type": "bbo", "coin": coin},
        {"type": "activeAssetCtx", "coin": coin},
        {"type": "candle", "coin": coin, "interval": "1m"},
    ]
    if deep:
        subscriptions.insert(1, {"type": "l2Book", "coin": coin})
    return subscriptions


def default_subscriptions() -> tuple[dict[str, Any], ...]:
    items = _coin_subscriptions(DEEP_COIN, deep=True)
    for coin in CONTEXT_COINS:
        items.extend(_coin_subscriptions(coin, deep=False))
    return tuple(items)


@dataclass(frozen=True, slots=True)
class RecorderConfig:
    ws_url: str = MAINNET_WS_URL
    network: str = NETWORK
    data_dir: Path = Path("data")
    queue_maxsize: int = 100_000
    health_interval_seconds: float = 60.0
    flush_interval_seconds: float = 1.0
    reconnect_initial_seconds: float = 1.0
    reconnect_max_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> RecorderConfig:
        data_dir = Path(os.getenv("HLP_DATA_DIR", "data")).expanduser()
        return cls(data_dir=data_dir)

    @property
    def subscriptions(self) -> tuple[dict[str, Any], ...]:
        return default_subscriptions()
