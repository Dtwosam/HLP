"""Robinhood Blockscout client for indexed historical acquisition.

Robinhood's official Blockscout instance exposes both modern REST endpoints
and the Etherscan-compatible legacy API. HLP uses the legacy logs endpoint for
topic-filtered history because it can query indexed history without scanning
every Robinhood block.

Raw on-chain facts remain canonical; Blockscout is an indexed transport for
those facts and every snapshot records its provenance.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from hlp.config import ROBINHOOD_CHAIN_ID, normalize_address
from hlp.data.types import RawLog


DEFAULT_BLOCKSCOUT_BASE = "https://robinhoodchain.blockscout.com"
BLOCKSCOUT_LOG_RESULT_LIMIT = 1000


class BlockscoutError(RuntimeError):
    pass


def _quantity(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    return int(text, 16) if text.startswith("0x") else int(text)


@dataclass(slots=True)
class BlockscoutClient:
    base_url: str = DEFAULT_BLOCKSCOUT_BASE
    timeout: float = 20.0
    attempts: int = 3
    backoff_seconds: float = 0.5
    transport: Callable[[urllib.request.Request, float], bytes] | None = None
    requests_made: int = field(default=0, init=False)
    bytes_received: int = field(default=0, init=False)

    def _read(self, request: urllib.request.Request) -> bytes:
        if self.transport is not None:
            return self.transport(request, self.timeout)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def _get(self, url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={"accept": "application/json", "user-agent": "hlp/0.1"},
        )
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                raw = self._read(request)
                self.requests_made += 1
                self.bytes_received += len(raw)
                return json.loads(raw)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                time.sleep(self.backoff_seconds * attempt)
        raise BlockscoutError(f"Blockscout request failed: {last_error}")

    def _legacy(self, module: str, action: str, **params: Any) -> Any:
        query = urllib.parse.urlencode(
            {"module": module, "action": action, **params}
        )
        return self._get(f"{self.base_url}/api?{query}")

    def block_number(self) -> int:
        payload = self._legacy("block", "eth_block_number")
        if str(payload.get("status")) != "1":
            raise BlockscoutError(f"block-number lookup failed: {payload}")
        value = payload.get("result")
        parsed = _quantity(value)
        if parsed is None:
            raise BlockscoutError(f"block-number lookup returned no result: {payload}")
        return parsed

    def contract_creation(self, address: str) -> dict[str, str]:
        address = normalize_address(address)
        payload = self._legacy(
            "contract",
            "getcontractcreation",
            contractaddresses=address,
        )
        if str(payload.get("status")) != "1":
            raise BlockscoutError(f"contract creation lookup failed: {payload}")
        rows = payload.get("result") or []
        if len(rows) != 1:
            raise BlockscoutError(
                f"expected exactly one creation record for {address}, got {len(rows)}"
            )
        row = rows[0]
        return {
            "contract_address": normalize_address(row["contractAddress"]),
            "creator": normalize_address(row["contractCreator"]),
            "transaction_hash": row["txHash"].lower(),
        }

    def transaction(self, tx_hash: str) -> dict[str, Any]:
        tx_hash = tx_hash.lower()
        payload = self._get(f"{self.base_url}/api/v2/transactions/{tx_hash}")
        if not isinstance(payload, dict) or "hash" not in payload:
            raise BlockscoutError(f"transaction lookup failed: {tx_hash}")
        return payload

    def contract_deployment(self, address: str) -> dict[str, Any]:
        creation = self.contract_creation(address)
        tx = self.transaction(creation["transaction_hash"])
        block = tx.get("block")
        if block is None:
            raise BlockscoutError(
                f"creation transaction has no mined block: {creation['transaction_hash']}"
            )
        return {
            **creation,
            "block_number": int(block),
            "timestamp": tx.get("timestamp"),
        }

    @staticmethod
    def _raw_log(row: dict[str, Any]) -> RawLog:
        block_number = _quantity(row.get("blockNumber"))
        log_index = _quantity(row.get("logIndex"))
        if block_number is None or log_index is None:
            raise BlockscoutError(f"log is missing block/log index: {row}")
        return RawLog(
            chain_id=ROBINHOOD_CHAIN_ID,
            block_number=block_number,
            block_hash=(row.get("blockHash") or "").lower() or None,
            transaction_hash=row["transactionHash"].lower(),
            transaction_index=_quantity(row.get("transactionIndex")),
            log_index=log_index,
            address=normalize_address(row["address"]),
            topics=tuple(str(topic).lower() for topic in row.get("topics", [])),
            data=(row.get("data") or "0x").lower(),
            removed=False,
        )

    def get_indexed_logs(
        self,
        from_block: int,
        to_block: int | str,
        *,
        address: str | None = None,
        topic0: str | None = None,
    ) -> list[RawLog]:
        """Fetch one Blockscout indexed-log response (maximum 1,000 rows)."""
        if isinstance(to_block, int) and to_block < from_block:
            raise ValueError("to_block must be >= from_block")
        if address is None and topic0 is None:
            raise ValueError("address or topic0 is required")

        params: dict[str, Any] = {
            "fromBlock": from_block,
            "toBlock": to_block,
        }
        if address is not None:
            params["address"] = normalize_address(address)
        if topic0 is not None:
            params["topic0"] = topic0.lower()

        payload = self._legacy("logs", "getLogs", **params)
        status = str(payload.get("status"))
        result = payload.get("result")

        # Blockscout/Etherscan-compatible instances commonly encode an empty
        # result as status=0/message='No logs found'. That is not an error.
        if status != "1":
            message = str(payload.get("message") or "").lower()
            result_text = str(result or "").lower()
            if "no logs" in message or "no logs" in result_text:
                return []
            raise BlockscoutError(
                f"indexed getLogs failed for {from_block}-{to_block}: {payload}"
            )

        if not isinstance(result, list):
            raise BlockscoutError(f"indexed getLogs returned non-list result: {payload}")

        rows = [self._raw_log(row) for row in result]
        rows.sort(
            key=lambda row: (
                row.block_number,
                -1 if row.transaction_index is None else row.transaction_index,
                row.log_index,
            )
        )
        return rows

    def iter_indexed_logs_bisect(
        self,
        from_block: int,
        to_block: int,
        *,
        address: str | None = None,
        topic0: str | None = None,
        result_limit: int = BLOCKSCOUT_LOG_RESULT_LIMIT,
        max_records: int | None = None,
    ) -> Iterator[RawLog]:
        """Yield complete ordered indexed logs without trusting a capped result.

        Blockscout documents at most 1,000 event logs per getLogs request.
        Any range returning the ceiling is therefore split in half until every
        leaf range is strictly below the cap. Splitting an exactly-1,000-result
        complete range is harmless and avoids silent truncation.

        Recursion visits the left range before the right range, preserving
        chronological order. A single block with >= result_limit matching logs
        cannot be made lossless through block splitting and fails closed.
        """
        if to_block < from_block:
            raise ValueError("to_block must be >= from_block")
        if result_limit < 2:
            raise ValueError("result_limit must be >= 2")
        if max_records is not None and max_records <= 0:
            return

        emitted = 0

        def walk(start: int, end: int) -> Iterator[RawLog]:
            nonlocal emitted
            if max_records is not None and emitted >= max_records:
                return
            rows = self.get_indexed_logs(
                start,
                end,
                address=address,
                topic0=topic0,
            )
            if len(rows) >= result_limit:
                if start == end:
                    raise BlockscoutError(
                        f"single block {start} has >= {result_limit} matching logs; "
                        "indexed getLogs cannot prove completeness"
                    )
                middle = (start + end) // 2
                yield from walk(start, middle)
                yield from walk(middle + 1, end)
                return

            for row in rows:
                if max_records is not None and emitted >= max_records:
                    return
                emitted += 1
                yield row

        yield from walk(from_block, to_block)
