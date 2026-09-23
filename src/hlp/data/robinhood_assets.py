"""Official Robinhood Stock Token asset-registry client.

Source:
https://api.robinhood.com/rhj/assets

This endpoint establishes canonical Stock Token identity. It is *not* used for
historical prices; historical valuation must come from point-in-time onchain
oracle data.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from hlp.config import ROBINHOOD_CHAIN_ID, normalize_address


DEFAULT_RHJ_ASSETS_URL = "https://api.robinhood.com/rhj/assets"


class RobinhoodAssetsError(RuntimeError):
    pass


@dataclass(slots=True)
class RobinhoodAssetsClient:
    url: str = DEFAULT_RHJ_ASSETS_URL
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

    def fetch_assets(self) -> list[dict[str, Any]]:
        request = urllib.request.Request(
            self.url,
            headers={"accept": "application/json", "user-agent": "hlp/0.1"},
        )
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                raw = self._read(request)
                self.requests_made += 1
                self.bytes_received += len(raw)
                payload = json.loads(raw)
                rows = payload.get("assets")
                if not isinstance(rows, list):
                    raise RobinhoodAssetsError("RHJ /assets response has no assets list")
                return rows
            except RobinhoodAssetsError:
                raise
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.attempts:
                    break
                time.sleep(self.backoff_seconds * attempt)
        raise RobinhoodAssetsError(f"RHJ /assets request failed: {last_error}")

    def canonical_chain_assets(self) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for asset in self.fetch_assets():
            deployments = asset.get("deployments") or []
            for deployment in deployments:
                if int(deployment.get("chainId", -1)) != ROBINHOOD_CHAIN_ID:
                    continue
                address = normalize_address(deployment["contractAddress"])
                if address in seen:
                    raise RobinhoodAssetsError(
                        f"duplicate Robinhood Chain asset deployment: {address}"
                    )
                seen.add(address)
                output.append(
                    {
                        "asset_id": str(asset.get("id") or "").lower(),
                        "token_symbol": str(asset.get("tokenSymbol") or ""),
                        "token_name": str(asset.get("tokenName") or ""),
                        "contract_address": address,
                        "chain_id": ROBINHOOD_CHAIN_ID,
                        "token_decimals": int(asset.get("tokenDecimals", 18)),
                        "status": str(asset.get("status") or ""),
                        "current_multiplier": str(asset.get("currentMultiplier") or ""),
                        "pending_multiplier": str(asset.get("pendingMultiplier") or ""),
                    }
                )
        output.sort(key=lambda row: (row["token_symbol"], row["contract_address"]))
        return output

    def address_map(self) -> dict[str, dict[str, Any]]:
        return {
            row["contract_address"]: row
            for row in self.canonical_chain_assets()
        }
