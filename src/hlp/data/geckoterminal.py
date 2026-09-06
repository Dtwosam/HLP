"""Minimal GeckoTerminal client for independent Phase 1 DEX cross-checks."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


DEFAULT_GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
GECKOTERMINAL_API_VERSION = "20230203"
GECKOTERMINAL_PUBLIC_CALLS_PER_MINUTE = 10
DEFAULT_GECKOTERMINAL_MIN_INTERVAL_SECONDS = 6.1
ROBINHOOD_GECKOTERMINAL_NETWORK = "robinhood"


class GeckoTerminalError(RuntimeError):
    pass


def _token_address(resource_id: str | None) -> str | None:
    if not resource_id:
        return None
    value = str(resource_id)
    if "_" not in value:
        return value.lower()
    return value.rsplit("_", 1)[-1].lower()


def _decimal_text(value: object | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)))


@dataclass(slots=True)
class GeckoTerminalClient:
    base_url: str = DEFAULT_GECKOTERMINAL_API
    timeout: float = 30.0
    attempts: int = 3
    min_interval_seconds: float = DEFAULT_GECKOTERMINAL_MIN_INTERVAL_SECONDS
    requests_made: int = field(default=0, init=False)
    bytes_received: int = field(default=0, init=False)
    _last_request_at: float | None = field(default=None, init=False)

    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict:
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds cannot be negative")
        if self.attempts <= 0:
            raise ValueError("attempts must be positive")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

        query = ""
        if params:
            query = "?" + urllib.parse.urlencode(params)
        url = self.base_url.rstrip("/") + path + query
        request = urllib.request.Request(
            url,
            headers={
                "accept": (
                    "application/json;version="
                    + GECKOTERMINAL_API_VERSION
                ),
                "user-agent": "hlp/0.1",
            },
        )

        def pace() -> None:
            if self._last_request_at is None:
                return
            elapsed = time.monotonic() - self._last_request_at
            wait = self.min_interval_seconds - elapsed
            if wait > 0:
                time.sleep(wait)

        def retry_after_seconds(exc: urllib.error.HTTPError) -> float:
            value = exc.headers.get("Retry-After") if exc.headers else None
            if value is None:
                return 0.0
            try:
                return max(float(value), 0.0)
            except ValueError:
                return 0.0

        retryable_http = {429, 500, 502, 503, 504}
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            pace()
            self._last_request_at = time.monotonic()
            self.requests_made += 1
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    raw = response.read()
                self.bytes_received += len(raw)
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise GeckoTerminalError(
                        "GeckoTerminal response is not an object"
                    )
                if payload.get("errors"):
                    raise GeckoTerminalError(
                        f"GeckoTerminal API error: {payload['errors']}"
                    )
                return payload
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in retryable_http or attempt == self.attempts:
                    break
                time.sleep(
                    max(
                        retry_after_seconds(exc),
                        min(2.0 * attempt, 5.0),
                    )
                )
            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                time.sleep(min(2.0 * attempt, 5.0))
        raise GeckoTerminalError(
            f"GeckoTerminal request failed: {last_error}"
        )

    def pool(
        self,
        pool_address: str,
        *,
        network: str = ROBINHOOD_GECKOTERMINAL_NETWORK,
    ) -> dict:
        payload = self._request(
            f"/networks/{network}/pools/{pool_address.lower()}"
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise GeckoTerminalError("pool response is missing data")
        attrs = data.get("attributes") or {}
        relationships = data.get("relationships") or {}
        base = ((relationships.get("base_token") or {}).get("data") or {})
        quote = ((relationships.get("quote_token") or {}).get("data") or {})
        address = str(attrs.get("address") or pool_address).lower()
        return {
            "network": network,
            "pool_address": address,
            "name": attrs.get("name"),
            "base_token": _token_address(base.get("id")),
            "quote_token": _token_address(quote.get("id")),
            "base_token_price_usd": _decimal_text(
                attrs.get("base_token_price_usd")
            ),
            "quote_token_price_usd": _decimal_text(
                attrs.get("quote_token_price_usd")
            ),
            "reserve_in_usd": _decimal_text(attrs.get("reserve_in_usd")),
            "pool_created_at": attrs.get("pool_created_at"),
        }

    def ohlcv(
        self,
        pool_address: str,
        *,
        timeframe: str = "minute",
        aggregate: int = 5,
        before_timestamp: int | None = None,
        limit: int = 1000,
        currency: str = "usd",
        token: str = "base",
        network: str = ROBINHOOD_GECKOTERMINAL_NETWORK,
    ) -> list[dict]:
        if timeframe not in {"minute", "hour", "day"}:
            raise ValueError("timeframe must be minute, hour, or day")
        allowed_aggregate = {
            "minute": {1, 5, 15},
            "hour": {1, 4, 12},
            "day": {1},
        }
        if aggregate not in allowed_aggregate[timeframe]:
            raise ValueError(
                f"invalid {timeframe} OHLCV aggregate: {aggregate}"
            )
        if not 1 <= limit <= 1000:
            raise ValueError("OHLCV limit must be between 1 and 1000")
        if currency not in {"usd", "token"}:
            raise ValueError("OHLCV currency must be usd or token")
        if token not in {"base", "quote"} and not token.startswith("0x"):
            raise ValueError(
                "OHLCV token must be base, quote, or a token address"
            )

        params: dict[str, Any] = {
            "aggregate": aggregate,
            "limit": limit,
            "currency": currency,
            "token": token,
            "include_empty_intervals": "false",
        }
        if before_timestamp is not None:
            if before_timestamp <= 0:
                raise ValueError("before_timestamp must be positive")
            params["before_timestamp"] = before_timestamp

        payload = self._request(
            (
                f"/networks/{network}/pools/{pool_address.lower()}"
                f"/ohlcv/{timeframe}"
            ),
            params,
        )
        data = payload.get("data")
        attrs = data.get("attributes") if isinstance(data, dict) else None
        raw_rows = attrs.get("ohlcv_list") if isinstance(attrs, dict) else None
        if not isinstance(raw_rows, list):
            raise GeckoTerminalError(
                "OHLCV response is missing data.attributes.ohlcv_list"
            )

        rows = []
        for raw in raw_rows:
            if not isinstance(raw, list) or len(raw) < 6:
                raise GeckoTerminalError(
                    f"invalid OHLCV row: {raw!r}"
                )
            rows.append(
                {
                    "timestamp": int(raw[0]),
                    "open": _decimal_text(raw[1]),
                    "high": _decimal_text(raw[2]),
                    "low": _decimal_text(raw[3]),
                    "close": _decimal_text(raw[4]),
                    "volume": _decimal_text(raw[5]),
                }
            )
        rows.sort(key=lambda row: row["timestamp"])
        return rows
