"""Robinhood Blockscout client for archive metadata and verification.

Blockscout is used as a bounded metadata/verification source, not as the
canonical high-frequency event tape.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from hlp.config import normalize_address


DEFAULT_BLOCKSCOUT_BASE = "https://robinhoodchain.blockscout.com"


class BlockscoutError(RuntimeError):
    pass


@dataclass(slots=True)
class BlockscoutClient:
    base_url: str = DEFAULT_BLOCKSCOUT_BASE
    timeout: float = 20.0

    def _get(self, url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={"accept": "application/json", "user-agent": "hlp/0.1"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read())

    def contract_creation(self, address: str) -> dict[str, str]:
        address = normalize_address(address)
        query = urllib.parse.urlencode(
            {
                "module": "contract",
                "action": "getcontractcreation",
                "contractaddresses": address,
            }
        )
        payload = self._get(f"{self.base_url}/api?{query}")
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
        timestamp = tx.get("timestamp")
        return {
            **creation,
            "block_number": int(block),
            "timestamp": timestamp,
        }
