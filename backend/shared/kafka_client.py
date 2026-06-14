"""
NITCC Async Kafka Client
Wraps aiokafka for producer/consumer functionality with Avro schema support.
Implements Appendix A — Agent Kafka Publisher/Consumer contracts.
"""

from __future__ import annotations
import asyncio
import json
import logging
import hashlib
from datetime import datetime
from typing import Callable, Awaitable, Optional, Any, Dict
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Kafka Topics (PRD Section 6.3 — partitioned by domain)
# ─────────────────────────────────────────────────────────────────────────────

class KafkaTopic:
    RAILWAY    = "nitcc.railway.events"
    WEATHER    = "nitcc.weather.events"
    SATELLITE  = "nitcc.satellite.events"
    LOGISTICS  = "nitcc.logistics.events"
    EMERGENCY  = "nitcc.emergency.events"
    ALERTS     = "nitcc.alerts"
    DEAD_LETTER = "nitcc.dead-letter"


# ─────────────────────────────────────────────────────────────────────────────
# Producer
# ─────────────────────────────────────────────────────────────────────────────

class NitccKafkaProducer:
    """
    Async Kafka producer with JSON serialization.
    Implements Appendix A: Topic: nitcc.{domain}.events; Key: agentId:eventType
    """

    def __init__(self, bootstrap_servers: str, agent_id: str):
        self._bootstrap_servers = bootstrap_servers
        self._agent_id = agent_id
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
            acks="all",
            enable_idempotence=True,
            compression_type="gzip",
        )
        await self._producer.start()
        logger.info(f"Kafka producer started for agent: {self._agent_id}")

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info(f"Kafka producer stopped for agent: {self._agent_id}")

    async def publish(
        self,
        topic: str,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        domain: str = "operational",
    ) -> None:
        """Publish event to Kafka topic with standard NITCC envelope."""
        if not self._producer:
            raise RuntimeError("Producer not started. Call start() first.")

        correlation_id = correlation_id or hashlib.md5(
            f"{self._agent_id}{event_type}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()

        message = {
            "agentId": self._agent_id,
            "eventType": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "correlationId": correlation_id,
            "domain": domain,
            "payload": payload,
            "schemaVersion": "2.0",
        }

        # Key convention per Appendix A: agentId:eventType
        key = f"{self._agent_id}:{event_type}"

        try:
            await self._producer.send_and_wait(topic, value=message, key=key)
            logger.debug(f"Published event [{event_type}] to topic [{topic}]")
        except KafkaError as e:
            logger.error(f"Kafka publish error [{topic}]: {e}")
            # Attempt dead-letter queue
            await self._send_to_dlq(topic, message, str(e))

    async def _send_to_dlq(
        self, original_topic: str, message: Dict, error: str
    ) -> None:
        """Send failed messages to dead-letter queue."""
        dlq_message = {
            "originalTopic": original_topic,
            "error": error,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            await self._producer.send_and_wait(
                KafkaTopic.DEAD_LETTER, value=dlq_message
            )
        except Exception:
            logger.exception("Failed to send to dead-letter queue")


# ─────────────────────────────────────────────────────────────────────────────
# Consumer
# ─────────────────────────────────────────────────────────────────────────────

class NitccKafkaConsumer:
    """
    Async Kafka consumer with per-agent consumer groups.
    Implements Appendix A: Group ID: {agentId}-consumer; Auto-offset: earliest on restart
    """

    def __init__(
        self,
        bootstrap_servers: str,
        agent_id: str,
        topics: list[str],
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
    ):
        self._bootstrap_servers = bootstrap_servers
        self._agent_id = agent_id
        self._topics = topics
        self._handler = handler
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._running = False

    async def start(self) -> None:
        # Group ID per Appendix A: {agentId}-consumer
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=self._bootstrap_servers,
            group_id=f"{self._agent_id}-consumer",
            auto_offset_reset="earliest",     # Appendix A: earliest on restart
            enable_auto_commit=False,          # Manual commit for reliability
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            max_poll_interval_ms=300000,
            session_timeout_ms=10000,
        )
        await self._consumer.start()
        self._running = True
        logger.info(
            f"Kafka consumer started for agent [{self._agent_id}] "
            f"on topics: {self._topics}"
        )

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info(f"Kafka consumer stopped for agent [{self._agent_id}]")

    async def consume(self) -> None:
        """Main consume loop — runs until stop() is called."""
        if not self._consumer:
            raise RuntimeError("Consumer not started. Call start() first.")

        async for msg in self._consumer:
            if not self._running:
                break
            try:
                await self._handler(msg.value)
                await self._consumer.commit()
            except Exception as e:
                logger.exception(
                    f"Error handling Kafka message [{msg.topic}@{msg.offset}]: {e}"
                )
                # Continue processing next message (don't crash the consumer)
