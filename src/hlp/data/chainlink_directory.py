"""Chainlink Robinhood feed-directory discovery.

Feed identities are discovered from Chainlink's official address directory.
Every discovered proxy must still be verified onchain before it is accepted
for historical pricing.
"""

from __future__ import annotations

import hashlib
import html
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable


DEFAULT_CHAINLINK_DIRECTORY_URL = (
    "https://docs.chain.link/data-feeds/price-feeds/addresses?network=robinhood"
)
_ADDRESS_RE = r"0x[a-fA-F0-9]{40}"


class ChainlinkDirectoryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RobinhoodFeedDirectoryEntry:
    symbol: str
    name: str
    path: str
    proxy_address: str
    secondary_proxy_address: str | None
    heartbeat_seconds: int
    blockchain_name: str


@dataclass(slots=True)
class ChainlinkDirectoryClient:
    url: str = DEFAULT_CHAINLINK_DIRECTORY_URL
    timeout: float = 30.0
    attempts: int = 3
    backoff_seconds: float = 0.5
    transport: Callable[[urllib.request.Request, float], bytes] | None = None
    requests_made: int = field(default=0, init=False)
    bytes_received: int = field(default=0, init=False)
    last_sha256: str | None = field(default=None, init=False)

    def _read(self, request: urllib.request.Request) -> bytes:
        if self.transport is not None:
            return self.transport(request, self.timeout)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def fetch_text(self) -> str:
        request = urllib.request.Request(
            self.url,
            headers={"accept": "text/html", "user-agent": "hlp/0.1"},
        )
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                raw = self._read(request)
                self.requests_made += 1
                self.bytes_received += len(raw)
                self.last_sha256 = hashlib.sha256(raw).hexdigest()
                return html.unescape(raw.decode("utf-8", errors="strict"))
            except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                time.sleep(self.backoff_seconds * attempt)
        raise ChainlinkDirectoryError(
            f"Chainlink directory request failed: {last_error}"
        )

    @staticmethod
    def _field(segment: str, name: str) -> str | None:
        match = re.search(
            rf'"{re.escape(name)}":\[0,"([^"]*)"\]',
            segment,
        )
        return match.group(1) if match else None

    @staticmethod
    def _int_field(segment: str, name: str) -> int | None:
        match = re.search(
            rf'"{re.escape(name)}":\[0,(\d+)\]',
            segment,
        )
        return int(match.group(1)) if match else None

    @staticmethod
    def parse_robinhood_feed(page_text: str, symbol: str) -> RobinhoodFeedDirectoryEntry:
        symbol = symbol.upper().strip()
        exact_name = f"Robinhood {symbol} / USD"
        marker = f'"name":[0,"{exact_name}"]'
        position = page_text.find(marker)
        if position < 0:
            raise ChainlinkDirectoryError(
                f"official Chainlink directory has no exact feed {exact_name!r}"
            )
        if page_text.find(marker, position + 1) >= 0:
            raise ChainlinkDirectoryError(
                f"official Chainlink directory contains duplicate feed {exact_name!r}"
            )

        # The server-rendered feed records place one heartbeat field before
        # each name. Bound the parse to adjacent heartbeat records so fields
        # from neighboring networks/feeds cannot bleed into this result.
        start = page_text.rfind('"heartbeat":[0,', 0, position)
        if start < 0:
            raise ChainlinkDirectoryError(f"{exact_name}: heartbeat boundary missing")
        end = page_text.find('"heartbeat":[0,', position + len(marker))
        if end < 0:
            end = min(len(page_text), position + 20_000)
        segment = page_text[start:end]

        name = ChainlinkDirectoryClient._field(segment, "name")
        path = ChainlinkDirectoryClient._field(segment, "path")
        proxy = ChainlinkDirectoryClient._field(segment, "proxyAddress")
        secondary = ChainlinkDirectoryClient._field(segment, "secondaryProxyAddress")
        heartbeat = ChainlinkDirectoryClient._int_field(segment, "heartbeat")
        blockchain = ChainlinkDirectoryClient._field(segment, "blockchainName")

        if name != exact_name:
            raise ChainlinkDirectoryError(
                f"{exact_name}: bounded record name mismatch: {name!r}"
            )
        if not path or not path.startswith(f"robinhood-{symbol.lower()}-usd-"):
            raise ChainlinkDirectoryError(
                f"{exact_name}: unexpected Chainlink path {path!r}"
            )
        if not proxy or not re.fullmatch(_ADDRESS_RE, proxy):
            raise ChainlinkDirectoryError(f"{exact_name}: proxy address missing")
        if secondary is not None and not re.fullmatch(_ADDRESS_RE, secondary):
            raise ChainlinkDirectoryError(
                f"{exact_name}: invalid secondary proxy {secondary!r}"
            )
        if heartbeat is None or heartbeat <= 0:
            raise ChainlinkDirectoryError(f"{exact_name}: invalid heartbeat")
        if blockchain != "Robinhood":
            raise ChainlinkDirectoryError(
                f"{exact_name}: blockchain mismatch {blockchain!r}"
            )

        return RobinhoodFeedDirectoryEntry(
            symbol=symbol,
            name=name,
            path=path,
            proxy_address=proxy.lower(),
            secondary_proxy_address=(
                secondary.lower() if secondary is not None else None
            ),
            heartbeat_seconds=heartbeat,
            blockchain_name=blockchain,
        )

    def robinhood_feeds(
        self,
        symbols: list[str] | tuple[str, ...] | set[str],
    ) -> list[RobinhoodFeedDirectoryEntry]:
        page = self.fetch_text()
        rows = [
            self.parse_robinhood_feed(page, symbol)
            for symbol in sorted({value.upper() for value in symbols})
        ]
        return rows
