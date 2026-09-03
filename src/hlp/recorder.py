from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
import uuid
from typing import Any

import websockets

from hlp.config import RecorderConfig
from hlp.health import HealthState
from hlp.storage import RawEventWriter

SCHEMA_VERSION = 1
LOGGER = logging.getLogger("hlp.recorder")


def _extract_coin(message: dict[str, Any]) -> str | None:
    data = message.get("data")

    if isinstance(data, dict):
        coin = data.get("coin")
        if isinstance(coin, str):
            return coin

        subscription = data.get("subscription")
        if isinstance(subscription, dict):
            coin = subscription.get("coin")
            if isinstance(coin, str):
                return coin

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("coin"), str):
                return item["coin"]

    return None


def _extract_exchange_time_ms(message: dict[str, Any]) -> int | None:
    data = message.get("data")

    def from_item(item: dict[str, Any]) -> int | None:
        for field in ("time", "t"):
            value = item.get(field)
            if isinstance(value, int):
                return value
        return None

    if isinstance(data, dict):
        return from_item(data)

    if isinstance(data, list):
        timestamps = [
            timestamp
            for item in data
            if isinstance(item, dict)
            for timestamp in [from_item(item)]
            if timestamp is not None
        ]
        if timestamps:
            return max(timestamps)

    return None


class MainnetRecorder:
    def __init__(self, config: RecorderConfig):
        self.config = config
        self.health = HealthState()
        self.queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=config.queue_maxsize
        )
        self.stop_event = asyncio.Event()

    async def run(self) -> None:
        writer_task = asyncio.create_task(self._writer_loop(), name="raw-writer")
        health_task = asyncio.create_task(self._health_loop(), name="health-reporter")

        try:
            await self._collector_loop()
        finally:
            await self.queue.put(None)
            await writer_task
            health_task.cancel()
            await asyncio.gather(health_task, return_exceptions=True)

    def request_stop(self) -> None:
        self.stop_event.set()

    async def _collector_loop(self) -> None:
        backoff = self.config.reconnect_initial_seconds
        first_attempt = True

        while not self.stop_event.is_set():
            connection_id = uuid.uuid4().hex
            sequence_local = 0

            try:
                async with websockets.connect(
                    self.config.ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                    max_queue=4096,
                ) as websocket:
                    self.health.connection_count += 1
                    await self._system_event(
                        connection_id,
                        sequence_local,
                        "connected",
                        {"ws_url": self.config.ws_url},
                    )
                    sequence_local += 1

                    for subscription in self.config.subscriptions:
                        await websocket.send(
                            json.dumps(
                                {"method": "subscribe", "subscription": subscription},
                                separators=(",", ":"),
                            )
                        )

                    backoff = self.config.reconnect_initial_seconds
                    first_attempt = False

                    while not self.stop_event.is_set():
                        try:
                            raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        except TimeoutError:
                            continue

                        received_ns = time.time_ns()
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")

                        try:
                            message = json.loads(raw)
                            if not isinstance(message, dict):
                                raise ValueError("top-level websocket payload is not an object")
                        except (json.JSONDecodeError, ValueError) as exc:
                            event = self._envelope(
                                connection_id=connection_id,
                                sequence_local=sequence_local,
                                channel="quarantine",
                                coin=None,
                                exchange_time_ms=None,
                                received_time_ns=received_ns,
                                payload={"raw": raw, "error": str(exc)},
                            )
                        else:
                            channel = str(message.get("channel") or "unknown")
                            coin = _extract_coin(message)
                            event = self._envelope(
                                connection_id=connection_id,
                                sequence_local=sequence_local,
                                channel=channel,
                                coin=coin,
                                exchange_time_ms=_extract_exchange_time_ms(message),
                                received_time_ns=received_ns,
                                payload=message,
                            )

                        self.health.mark_message(event["channel"], event["coin"], received_ns)
                        await self.queue.put(event)
                        sequence_local += 1

            except asyncio.CancelledError:
                raise
            except Exception as exc:  # network boundary: record and reconnect
                self.health.reconnect_count += 0 if first_attempt else 1
                received_ns = time.time_ns()
                await self.queue.put(
                    self._envelope(
                        connection_id=connection_id,
                        sequence_local=sequence_local,
                        channel="system",
                        coin=None,
                        exchange_time_ms=None,
                        received_time_ns=received_ns,
                        payload={
                            "event": "connection_error",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "retry_in_seconds": backoff,
                        },
                    )
                )
                LOGGER.warning("connection error; retrying in %.1fs: %s", backoff, exc)

                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=backoff)
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, self.config.reconnect_max_seconds)

    async def _system_event(
        self,
        connection_id: str,
        sequence_local: int,
        event_name: str,
        details: dict[str, Any],
    ) -> None:
        received_ns = time.time_ns()
        await self.queue.put(
            self._envelope(
                connection_id=connection_id,
                sequence_local=sequence_local,
                channel="system",
                coin=None,
                exchange_time_ms=None,
                received_time_ns=received_ns,
                payload={"event": event_name, **details},
            )
        )

    def _envelope(
        self,
        *,
        connection_id: str,
        sequence_local: int,
        channel: str,
        coin: str | None,
        exchange_time_ms: int | None,
        received_time_ns: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "network": self.config.network,
            "source": "hyperliquid_websocket",
            "channel": channel,
            "coin": coin,
            "exchange_time_ms": exchange_time_ms,
            "received_time_ns": received_time_ns,
            "connection_id": connection_id,
            "sequence_local": sequence_local,
            "payload": payload,
        }

    async def _writer_loop(self) -> None:
        writer = RawEventWriter(
            self.config.data_dir,
            self.config.network,
            self.config.flush_interval_seconds,
        )
        try:
            while True:
                event = await self.queue.get()
                if event is None:
                    self.queue.task_done()
                    break
                try:
                    writer.write(event)
                except Exception:
                    self.health.write_errors += 1
                    LOGGER.exception("raw event write failed")
                    raise
                finally:
                    self.queue.task_done()
        finally:
            writer.close()

    async def _health_loop(self) -> None:
        while True:
            await asyncio.sleep(self.config.health_interval_seconds)
            LOGGER.info(
                "health %s",
                json.dumps(
                    self.health.snapshot(queue_depth=self.queue.qsize()),
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )


async def _run() -> None:
    config = RecorderConfig.from_env()
    recorder = MainnetRecorder(config)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, recorder.request_stop)
        except NotImplementedError:
            pass

    await recorder.run()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
