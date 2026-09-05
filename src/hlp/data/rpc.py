"""Minimal dependency-light Ethereum JSON-RPC client.

The client intentionally exposes raw primitives. Protocol-specific decoding
belongs in adapters so source semantics stay testable and versioned.
"""

from __future__ import annotations

import http.client
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
    min_interval_seconds: float = 0.0
    extra_headers: dict[str, str] | None = None
    transport: Callable[[urllib.request.Request, float], bytes] | None = None
    route_label: str = "unclassified"
    requests_made: int = field(default=0, init=False)
    response_bytes_received: int = field(default=0, init=False)
    _last_request_at: float | None = field(default=None, init=False, repr=False)

    def _post(self, request: urllib.request.Request, timeout: float) -> bytes:
        if self.transport is not None:
            return self.transport(request, timeout)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def _pace(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        now = time.monotonic()
        if self._last_request_at is not None:
            wait = self.min_interval_seconds - (now - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _retry_after_seconds(exc: urllib.error.HTTPError) -> float | None:
        if exc.code != 429:
            return None
        value = exc.headers.get("Retry-After") if exc.headers is not None else None
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
            separators=(",", ":"),
        ).encode()
        headers = {"content-type": "application/json", "user-agent": "hlp/0.1"}
        if self.extra_headers:
            headers.update(self.extra_headers)
        request = urllib.request.Request(
            self.url,
            data=body,
            headers=headers,
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                self._pace()
                self.requests_made += 1
                response_bytes = self._post(request, self.timeout)
                self.response_bytes_received += len(response_bytes)
                payload = json.loads(response_bytes)
                if "error" in payload:
                    raise RpcError(f"{method}: {payload['error']}")
                if "result" not in payload:
                    raise RpcError(f"{method}: malformed JSON-RPC response")
                return payload["result"]
            except urllib.error.HTTPError as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                retry_after = self._retry_after_seconds(exc)
                time.sleep(
                    retry_after
                    if retry_after is not None
                    else self.backoff_seconds * attempt
                )
            except RpcError:
                # A JSON-RPC response error (bad params, provider range cap,
                # unsupported history, revert, etc.) already reached a node.
                # Blind retries waste quota and cannot repair a deterministic
                # request. Higher-level callers may adapt the request shape.
                raise
            except (
                urllib.error.URLError,
                TimeoutError,
                http.client.IncompleteRead,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                time.sleep(self.backoff_seconds * attempt)
        raise RpcError(f"{method} failed after {self.attempts} attempts: {last_error}")

    def batch_call(
        self,
        calls: list[tuple[str, list[Any] | None]],
    ) -> list[Any]:
        """Execute one JSON-RPC batch HTTP request and preserve call order."""
        if not calls:
            return []
        body = json.dumps(
            [
                {
                    "jsonrpc": "2.0",
                    "id": index + 1,
                    "method": method,
                    "params": params or [],
                }
                for index, (method, params) in enumerate(calls)
            ],
            separators=(",", ":"),
        ).encode()
        headers = {"content-type": "application/json", "user-agent": "hlp/0.1"}
        if self.extra_headers:
            headers.update(self.extra_headers)
        request = urllib.request.Request(
            self.url,
            data=body,
            headers=headers,
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                self._pace()
                self.requests_made += 1
                response_bytes = self._post(request, self.timeout)
                self.response_bytes_received += len(response_bytes)
                payload = json.loads(response_bytes)
                if not isinstance(payload, list):
                    raise RpcError("batch JSON-RPC response is not a list")
                by_id = {}
                for item in payload:
                    if "error" in item:
                        raise RpcError(f"batch call error: {item['error']}")
                    if "id" not in item or "result" not in item:
                        raise RpcError("malformed batch JSON-RPC response")
                    by_id[int(item["id"])] = item["result"]
                expected = set(range(1, len(calls) + 1))
                if set(by_id) != expected:
                    raise RpcError("batch JSON-RPC response ids are incomplete")
                return [by_id[index] for index in range(1, len(calls) + 1)]
            except urllib.error.HTTPError as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                retry_after = self._retry_after_seconds(exc)
                time.sleep(
                    retry_after
                    if retry_after is not None
                    else self.backoff_seconds * attempt
                )
            except RpcError:
                raise
            except (
                urllib.error.URLError,
                TimeoutError,
                http.client.IncompleteRead,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                time.sleep(self.backoff_seconds * attempt)
        raise RpcError(
            f"batch call failed after {self.attempts} attempts: {last_error}"
        )

    def get_blocks_batched(
        self,
        blocks: list[int],
        *,
        full_transactions: bool = False,
        batch_size: int = 100,
        min_batch_size: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch many blocks with adaptive JSON-RPC batch shrinking."""
        if batch_size < 1 or min_batch_size < 1 or min_batch_size > batch_size:
            raise ValueError("invalid batch sizes")
        if any(block < 0 for block in blocks):
            raise ValueError("block numbers cannot be negative")
        if not blocks:
            return []

        output: list[dict[str, Any]] = []
        cursor = 0
        target_size = batch_size
        active_size = target_size
        while cursor < len(blocks):
            chunk = blocks[cursor : cursor + active_size]
            calls = [
                (
                    "eth_getBlockByNumber",
                    [_hex_quantity(block), full_transactions],
                )
                for block in chunk
            ]
            try:
                results = self.batch_call(calls)
            except RpcError:
                if active_size <= min_batch_size:
                    # Some providers disable JSON-RPC batching entirely.
                    # A single regular call is the most compatible fallback.
                    if active_size == 1:
                        output.append(
                            self.get_block(
                                chunk[0],
                                full_transactions=full_transactions,
                            )
                        )
                        cursor += 1
                        active_size = target_size
                        continue
                    raise
                active_size = max(min_batch_size, active_size // 2)
                continue

            for block, result in zip(chunk, results):
                if result is None:
                    raise RpcError(f"block not found in batch: {block}")
                output.append(result)
            cursor += len(chunk)
            if active_size < target_size:
                active_size = min(target_size, active_size * 2)

        return output

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

    def get_transaction(self, transaction_hash: str) -> dict[str, Any]:
        result = self.call("eth_getTransactionByHash", [transaction_hash])
        if result is None:
            raise RpcError(f"transaction not found: {transaction_hash}")
        return result

    def get_transactions_batched(
        self,
        transaction_hashes: list[str],
        *,
        batch_size: int = 100,
        min_batch_size: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch many transactions with adaptive JSON-RPC batch shrinking."""
        if batch_size < 1 or min_batch_size < 1 or min_batch_size > batch_size:
            raise ValueError("invalid batch sizes")
        if not transaction_hashes:
            return []

        output: list[dict[str, Any]] = []
        cursor = 0
        target_size = batch_size
        active_size = target_size
        while cursor < len(transaction_hashes):
            chunk = transaction_hashes[cursor : cursor + active_size]
            calls = [
                ("eth_getTransactionByHash", [transaction_hash])
                for transaction_hash in chunk
            ]
            try:
                results = self.batch_call(calls)
            except RpcError:
                if active_size <= min_batch_size:
                    if active_size == 1:
                        output.append(self.get_transaction(chunk[0]))
                        cursor += 1
                        active_size = target_size
                        continue
                    raise
                active_size = max(min_batch_size, active_size // 2)
                continue

            for transaction_hash, result in zip(chunk, results):
                if result is None:
                    raise RpcError(
                        f"transaction not found in batch: {transaction_hash}"
                    )
                output.append(result)
            cursor += len(chunk)
            if active_size < target_size:
                active_size = min(target_size, active_size * 2)
        return output

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
        error, and grows back only after eight consecutive successful windows.
        The streak prevents a dense range from oscillating between one known
        good window and the immediately larger request the provider rejects.
        """
        if to_block < from_block:
            raise ValueError("to_block must be >= from_block")
        if chunk_size < 1 or min_chunk_size < 1 or min_chunk_size > chunk_size:
            raise ValueError("invalid chunk sizes")

        cursor = from_block
        target_size = chunk_size
        active_size = target_size
        successful_windows = 0
        grow_after_successes = 8
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
                successful_windows = 0
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
                successful_windows += 1
                if successful_windows >= grow_after_successes:
                    active_size = min(target_size, active_size * 2)
                    successful_windows = 0
            else:
                successful_windows = 0

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
