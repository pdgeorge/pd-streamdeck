"""
RabbitMQ publisher for deck buttons.

Follows the convention already in use across the dabiverse: fanout exchanges,
durable, event name in the AMQP `type` property, JSON body. Consumers filter
on `message.type` themselves, so a deck button can drop an event that an
existing service already handles without that service changing at all.

Publishing is best-effort: the broker being down should grey out one button,
not stop the deck from switching scenes.
"""

import asyncio
import json
import logging
import os
from typing import Optional

import aio_pika

LOGGER = logging.getLogger("deck.bus")

RECONNECT_MIN = 2
RECONNECT_MAX = 30


class BusError(Exception):
    """Not connected, or the exchange isn't one we publish to."""


class Bus:
    def __init__(self, url: str, exchange_names: list[str]):
        self._url = url
        self._exchange_names = exchange_names
        self._connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
        self._channel = None
        self._exchanges: dict[str, aio_pika.abc.AbstractExchange] = {}
        self._task: Optional[asyncio.Task] = None
        self._stopping = False
        self.connected = False
        self.last_error: Optional[str] = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._supervise(), name="bus-supervisor")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._connection and not self._connection.is_closed:
            await self._connection.close()

    async def _supervise(self) -> None:
        backoff = RECONNECT_MIN
        while not self._stopping:
            try:
                # connect_robust reconnects underneath us, so a successful
                # connect normally means we just park here forever.
                self._connection = await aio_pika.connect_robust(self._url)
                self._channel = await self._connection.channel()
                self._exchanges = {
                    name: await self._channel.declare_exchange(
                        name, aio_pika.ExchangeType.FANOUT, durable=True
                    )
                    for name in self._exchange_names
                }
                self.connected = True
                self.last_error = None
                backoff = RECONNECT_MIN
                LOGGER.info("Bus ready; exchanges: %s", ", ".join(self._exchanges))

                while not self._connection.is_closed and not self._stopping:
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry on anything
                self.last_error = str(exc)
                LOGGER.info("RabbitMQ unavailable (%s); retrying in %ss", exc, backoff)
            finally:
                self.connected = False
                self._exchanges = {}

            if self._stopping:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX)

    async def publish(
        self, exchange: str, event_type: str, payload: Optional[dict] = None
    ) -> dict:
        if not self.connected:
            raise BusError(f"RabbitMQ is not connected ({self.last_error or 'no reason given'})")

        target = self._exchanges.get(exchange)
        if target is None:
            known = ", ".join(self._exchanges) or "none"
            raise BusError(f"Unknown exchange {exchange!r}. Configured: {known}")

        message = aio_pika.Message(
            body=json.dumps(payload or {}).encode(),
            type=event_type,
            content_type="application/json",
        )
        await target.publish(message, routing_key="")
        LOGGER.info("Published %s to %s", event_type, exchange)
        return {"exchange": exchange, "type": event_type}

    def snapshot(self) -> dict:
        return {
            "connected": self.connected,
            "exchanges": list(self._exchanges),
            "error": self.last_error if not self.connected else None,
        }


def build_bus() -> Bus:
    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    exchanges = [
        os.getenv("TWITCH_EXCHANGE", "twitch_events"),
        os.getenv("DABI_EXCHANGE", "dabi_events"),
    ]
    return Bus(url, exchanges)
