"""Barramento de eventos: Kafka em produção, memória em testes e em dev sem infraestrutura."""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Awaitable, Callable

from pydantic import BaseModel

from morbidus_common.settings import ServiceSettings

Handler = Callable[[dict], Awaitable[None]]
log = logging.getLogger(__name__)


class EventBus:
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def publish(self, topic: str, event: BaseModel, key: str | None = None) -> None:
        raise NotImplementedError

    def subscribe(self, topic: str, handler: Handler) -> None:
        raise NotImplementedError


class InMemoryBus(EventBus):
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self.published: list[tuple[str, dict]] = []

    async def publish(self, topic: str, event: BaseModel, key: str | None = None) -> None:
        payload = event.model_dump(mode="json")
        self.published.append((topic, payload))
        for handler in list(self._handlers[topic]):
            await handler(payload)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)


class KafkaBus(EventBus):
    """Consumidor com commit manual: o offset só avança depois do handler.

    Evento que falha vai para `<tópico>.dlq` em vez de travar a partição.
    """

    def __init__(self, bootstrap: str, group_id: str, connect_retries: int = 15) -> None:
        self._bootstrap = bootstrap
        self._group_id = group_id
        self._connect_retries = connect_retries
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._producer = None
        self._consumer = None
        self._task: asyncio.Task | None = None

    async def _retry(self, start: Callable[[], Awaitable[None]], what: str) -> None:
        for attempt in range(1, self._connect_retries + 1):
            try:
                await start()
                return
            except Exception:
                if attempt == self._connect_retries:
                    raise
                log.warning("kafka indisponível (%s), tentativa %d", what, attempt)
                await asyncio.sleep(min(2 * attempt, 10))

    async def start(self) -> None:
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
            key_serializer=lambda k: k.encode() if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await self._retry(self._producer.start, "producer")
        if self._handlers:
            self._consumer = AIOKafkaConsumer(
                *self._handlers.keys(),
                bootstrap_servers=self._bootstrap,
                group_id=self._group_id,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
                value_deserializer=lambda v: json.loads(v),
            )
            await self._retry(self._consumer.start, "consumer")
            self._task = asyncio.create_task(self._consume())

    async def _consume(self) -> None:
        async for msg in self._consumer:
            for handler in self._handlers[msg.topic]:
                try:
                    await handler(msg.value)
                except Exception:
                    log.exception("falha ao processar evento de %s; enviando para DLQ", msg.topic)
                    await self._producer.send_and_wait(f"{msg.topic}.dlq", msg.value)
            await self._consumer.commit()

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._consumer:
            await self._consumer.stop()
        if self._producer:
            await self._producer.stop()

    async def publish(self, topic: str, event: BaseModel, key: str | None = None) -> None:
        await self._producer.send_and_wait(topic, event.model_dump(mode="json"), key=key)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)


def make_bus(settings: ServiceSettings, group_id: str) -> EventBus:
    if settings.bus_backend == "kafka":
        return KafkaBus(settings.kafka_bootstrap, group_id)
    return InMemoryBus()
