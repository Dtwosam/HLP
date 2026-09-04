"""Minimal dependency-light Ethereum JSON-RPC client.

The client intentionally exposes raw primitives. Protocol-specific decoding
belongs in adapters so source semantics stay testable and versioned.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from hlp.config import ROBINHOOD_CHAIN_ID
from hlp.data.types import RawLog


class RpcError(RuntimeError):
    pass


def _hex_quantity(value: int | str) -> str:
    if isinstance(value, str):
        if value in {"latest", "earliest", "pending", "safe", "finalized"}:
            return value
        if value.startswith("0x"):
            return value
        value = int(value)
    if value < 0:
        raise ValueError("RPC block quantities cannot be negative")
    return hex(value)


@dataclass(slots=True)
class RpcClient:
    url: str
    timeout: float = 20.0
    attempts: int = 3
    backoff_seconds: float = 0.5
    transport: Callable[[urllib.request.Request, float], bytes] | None = None
    requests_made: int = field(default=0, init=False)

    def _post(self, request: urllib.request.Request, timeout: float) -> bytes:
        if self.transport is not None:
            return self.transport(request, timeout)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
            separators=(",", ":"),
        ).encode()
        request = urllib.request.Request(
            self.url,
            data=body,
            headers={"content-type": "application/json", "user-agent": "hlp/0.1"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                self.requests_made += 1
                payload = json.loads(self._post(request, self.timeout))
                if "error" in payload:
                    raise RpcError(f"{method}: {payload['error']}")
                if "result" not in payload:
                    raise RpcError(f"{method}: malformed JSON-RPC response")
                return payload["result"]
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RpcError) as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                time.sleep(self.backoff_seconds * attempt)
        raise RpcError(f"{method} failed after {self.attempts} attempts: {last_error}")

    def chain_id(self) -> int:
        return int(self.call("eth_chainId"), 16)

    def assert_robinhood(self) -> None:
        observed = self.chain_id()
        if observed != ROBINHOOD_CHAIN_ID:
            raise RpcError(
                f"wrong chain: expected {ROBINHOOD_CHAIN_ID}, observed {observed}"
            )

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber"), 16)

    def get_block(self, block: int | str = "latest", full_transactions: bool = False) -> dict[str, Any]:
        result = self.call("eth_getBlockByNumber", [_hex_quantity(block), full_transactions])
        if result is None:
            raise RpcError(f"block not found: {block}")
        return result

    def get_code(self, address: str, block: int | str = "latest") -> str:
        return self.call("eth_getCode", [address, _hex_quantity(block)])

    def eth_call(
        self,
        to: str,
        data: str,
        block: int | str = "latest",
    ) -> str:
        return self.call(
            "eth_call",
            [{"to": to, "data": data}, _hex_quantity(block)],
        )

    def find_first_code_block(
        self,
        address: str,
        *,
        low: int = 0,
        high: int | None = None,
    ) -> int:
        """Binary-search the first block where an address has bytecode.

        This assumes code presence is monotonic for the address in the search
        interval, which is valid for ordinary non-self-destructed deployments.
        Callers should independently verify the returned boundary.
        """
        if high is None:
            high = self.block_number()
        if low < 0 or high < low:
            raise ValueError("invalid deployment search interval")
        if self.get_code(address, high) in {"0x", "0x0", ""}:
            raise RpcError(f"address has no bytecode at high block {high}: {address}")
        while low < high:
            mid = (low + high) // 2
            code = self.get_code(address, mid)
            if code not in {"0x", "0x0", ""}:
                high = mid
            else:
                low = mid + 1
        return low

    def iter_logs_chunked(
        self,
        from_block: int,
        to_block: int,
        *,
        address: str | list[str] | None = None,
        topics: list[Any] | None = None,
        chunk_size: int = 100_000,
        min_chunk_size: int = 1,
    ):
        """Yield logs over an inclusive range with adaptive range shrinking.

        Providers disagree sharply on eth_getLogs range limits. HLP starts
        with the caller's preferred window, halves it after a terminal RPC
        error, and cautiously grows back after successful windows.
        """
        if to_block < from_block:
            raise ValueError("to_block must be >= from_block")
        if chunk_size < 1 or min_chunk_size < 1 or min_chunk_size > chunk_size:
            raise ValueError("invalid chunk sizes")

        cursor = from_block
        target_size = chunk_size
        active_size = target_size
        while cursor <= to_block:
            end = min(to_block, cursor + active_size - 1)
            try:
                rows = self.get_logs(
                    cursor,
                    end,
                    address=address,
                    topics=topics,
                )
            except RpcError:
                if active_size <= min_chunk_size:
                    raise
                active_size = max(min_chunk_size, active_size // 2)
                continue

            rows.sort(
                key=lambda row: (
                    row.block_number,
                    -1 if row.transaction_index is None else row.transaction_index,
                    row.log_index,
                )
            )
            yield from rows
            cursor = end + 1
            if active_size < target_size:
                active_size = min(target_size, active_size * 2)

    def get_logs(
        self,
        from_block: int,
        to_block: int,
        *,
        address: str | list[str] | None = None,
        topics: list[Any] | None = None,
    ) -> list[RawLog]:
        if to_block < from_block:
            raise ValueError("to_block must be >= from_block")
        query: dict[str, Any] = {
            "fromBlock": _hex_quantity(from_block),
            "toBlock": _hex_quantity(to_block),
        }
        if address is not None:
            query["address"] = address
        if topics is not None:
            query["topics"] = topics
        result = self.call("eth_getLogs", [query])
        return [RawLog.from_rpc(ROBINHOOD_CHAIN_ID, item) for item in result]
