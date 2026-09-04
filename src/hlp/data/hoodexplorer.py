"""hoodexplorer archive/index API client for Robinhood Chain.

hoodexplorer exposes an Etherscan-compatible indexed API plus a proxy to its
archive node. HLP uses it as a zero-cost historical acquisition candidate.

Canonical research still stores raw facts locally with provenance so this
provider can be replaced/replayed later.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from hlp.config import ROBINHOOD_CHAIN_ID, normalize_address
from hlp.data.types import RawLog


DEFAULT_HOOD_API = "https://hoodexplorer.org/api"


class HoodExplorerError(RuntimeError):
    pass


def _parse_quantity(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    if text.startswith("0x"):
        return int(text, 16)
    return int(text)


@dataclass(slots=True)
class HoodExplorerClient:
    base_url: str = DEFAULT_HOOD_API
    timeout: float = 30.0
    attempts: int = 3
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.api_key is None:
            self.api_key = os.environ.get("HOODEXPLORER_API_KEY") or None

    def _request(self, params: dict[str, Any]) -> Any:
        query = dict(params)
        if self.api_key:
            query["apikey"] = self.api_key
        url = f"{self.base_url}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(
            url,
            headers={"accept": "application/json", "user-agent": "hlp/0.1"},
        )
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read())
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                time.sleep(0.5 * attempt)
        raise HoodExplorerError(f"hoodexplorer request failed: {last_error}")

    def call(self, module: str, action: str, **params: Any) -> Any:
        payload = self._request({"module": module, "action": action, **params})
        if str(payload.get("status")) != "1":
            raise HoodExplorerError(
                f"hoodexplorer {module}/{action} failed: "
                f"{payload.get('message')}: {payload.get('result')}"
            )
        return payload.get("result")

    def proxy_call(self, method: str, params: list[Any] | None = None) -> Any:
        payload = self._request(
            {
                "module": "proxy",
                "action": method,
                "params": json.dumps(params or [], separators=(",", ":")),
            }
        )
        if "error" in payload:
            raise HoodExplorerError(f"hoodexplorer proxy {method}: {payload['error']}")
        if "result" not in payload:
            raise HoodExplorerError(f"hoodexplorer proxy {method}: malformed response")
        return payload["result"]

    def contract_creation(self, address: str) -> dict[str, str]:
        address = normalize_address(address)
        rows = self.call(
            "contract",
            "getcontractcreation",
            contractaddresses=address,
        )
        if len(rows) != 1:
            raise HoodExplorerError(
                f"expected one creation record for {address}, got {len(rows)}"
            )
        row = rows[0]
        return {
            "contract_address": normalize_address(row["contractAddress"]),
            "creator": normalize_address(row["contractCreator"]),
            "transaction_hash": row["txHash"].lower(),
        }

    def transaction(self, tx_hash: str) -> dict[str, Any]:
        result = self.proxy_call("eth_getTransactionByHash", [tx_hash])
        if result is None:
            raise HoodExplorerError(f"transaction not found: {tx_hash}")
        return result

    def contract_deployment(self, address: str) -> dict[str, Any]:
        creation = self.contract_creation(address)
        tx = self.transaction(creation["transaction_hash"])
        block = _parse_quantity(tx.get("blockNumber"))
        if block is None:
            raise HoodExplorerError(
                f"creation transaction not mined: {creation['transaction_hash']}"
            )
        return {**creation, "block_number": block}

    def get_code(self, address: str, block: int | str = "latest") -> str:
        block_param = block if isinstance(block, str) else hex(block)
        return self.proxy_call("eth_getCode", [address, block_param])

    def get_logs_page(
        self,
        *,
        address: str | None = None,
        topic0: str | None = None,
        from_block: int = 0,
        to_block: int | str = "latest",
        page: int = 1,
        offset: int = 1000,
        sort: str = "asc",
    ) -> list[RawLog]:
        if address is None and topic0 is None:
            raise ValueError("address or topic0 is required")
        if not 1 <= offset <= 1000:
            raise ValueError("offset must be between 1 and 1000")
        if sort not in {"asc", "desc"}:
            raise ValueError("sort must be asc or desc")
        params: dict[str, Any] = {
            "fromBlock": from_block,
            "toBlock": to_block,
            "page": page,
            "offset": offset,
            "sort": sort,
        }
        if address is not None:
            params["address"] = normalize_address(address)
        if topic0 is not None:
            params["topic0"] = topic0.lower()
        rows = self.call("logs", "getlogs", **params)
        result: list[RawLog] = []
        for row in rows:
            result.append(
                RawLog(
                    chain_id=ROBINHOOD_CHAIN_ID,
                    block_number=int(_parse_quantity(row["blockNumber"])),
                    block_hash=(row.get("blockHash") or "").lower() or None,
                    transaction_hash=row["transactionHash"].lower(),
                    transaction_index=_parse_quantity(row.get("transactionIndex")),
                    log_index=int(_parse_quantity(row["logIndex"])),
                    address=normalize_address(row["address"]),
                    topics=tuple(topic.lower() for topic in row.get("topics", [])),
                    data=(row.get("data") or "0x").lower(),
                    removed=False,
                )
            )
        return result

    def token_info(self, token: str) -> dict[str, Any]:
        rows = self.call("token", "tokeninfo", contractaddress=normalize_address(token))
        if not rows:
            raise HoodExplorerError(f"token not indexed: {token}")
        return rows[0]
