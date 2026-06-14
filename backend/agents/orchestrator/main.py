"""
NITCC Orchestrator Agent — Main FastAPI Microservice
Domain: Multi-Agent Coordination
PRD FR-01: LangGraph state machine, global belief state, orchestration loops
"""

from __future__ import annotations
import asyncio
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Gauge, Histogram

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import settings
from shared.mongodb import connect_db, disconnect_db
from shared.redis_client import connect_redis, disconnect_redis, set_agent_state
from shared.kafka_client import NitccKafkaProducer, NitccKafkaConsumer, KafkaTopic
from shared.schemas.models import AgentStatus

from .langgraph_machine import NITCCStateMachine

log = structlog.get_logger()
AGENT_ID = "orchestrator-agent"
AGENT_NAME = "NITCC Orchestrator Agent"

CYCLES_TOTAL = Counter("nitcc_orchestrator_cycles_total", "Orchestration cycles executed")
CYCLE_DURATION = Histogram("nitcc_orchestrator_cycle_duration_seconds", "Cycle duration")
ERROR_RATE = Counter("nitcc_orchestrator_errors_total", "Errors")
AGENT_STATUS_GAUGE = Gauge("nitcc_orchestrator_status", "Agent status")

_state_machine: NITCCStateMachine = None
_producer: NitccKafkaProducer = None
_start_time: float = 0.0

# Events queue for batching
_pending_events: list = []


async def _kafka_event_handler(event: dict) -> None:
    """Collect events from all domains for orchestration cycle."""
    _pending_events.append(event)
    # Limit buffer size
    if len(_pending_events) > 100:
        _pending_events.pop(0)


async def _orchestration_loop():
    """
    Main orchestration cycle: runs every 5 minutes (FR-09).
    Processes all domain events, updates NRI, coordinates agents.
    """
    while True:
        try:
            start = time.time()
            events_batch = _pending_events.copy()
            _pending_events.clear()

            final_state = await _state_machine.run_orchestration_cycle(events_batch)

            elapsed = time.time() - start
            CYCLE_DURATION.observe(elapsed)
            CYCLES_TOTAL.inc()

            log.info(
                "Orchestration cycle complete",
                nri=final_state.get("national_risk_index", 0),
                elapsed_s=round(elapsed, 2),
                p1=final_state.get("p1_active", False),
                p2=final_state.get("p2_active", False),
            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            log.error("Orchestration cycle error", error=str(e))

        await asyncio.sleep(5 * 60)  # Every 5 minutes


async def _heartbeat_loop():
    while True:
        try:
            await set_agent_state(AGENT_ID, {
                "agentId": AGENT_ID,
                "agentName": AGENT_NAME,
                "status": AgentStatus.RUNNING.value,
                "lastHeartbeat": datetime.utcnow().isoformat(),
                "uptime_s": round(time.time() - _start_time, 1),
            })
        except asyncio.CancelledError:
            break
        except Exception:
            pass
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _state_machine, _producer, _start_time
    _start_time = time.time()
    log.info(f"{AGENT_NAME} starting...")
    try:
        await connect_db(settings.mongodb_uri, settings.mongodb_db_name)
    except Exception as e:
        log.error(f"MongoDB connection failed: {e}")
    try:
        await connect_redis(settings.redis_url, settings.redis_password)
    except Exception as e:
        log.error(f"Redis connection failed: {e}")

    tasks = []
    try:
        _producer = NitccKafkaProducer(settings.kafka_bootstrap_servers, AGENT_ID)
        await _producer.start()

        _state_machine = NITCCStateMachine(producer=_producer)

        # Subscribe to ALL domain events
        consumer = NitccKafkaConsumer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            agent_id=AGENT_ID,
            topics=[
                KafkaTopic.RAILWAY,
                KafkaTopic.WEATHER,
                KafkaTopic.SATELLITE,
                KafkaTopic.LOGISTICS,
                KafkaTopic.EMERGENCY,
            ],
            handler=_kafka_event_handler,
        )
        await consumer.start()

        tasks = [
            asyncio.create_task(consumer.consume(), name="kafka"),
            asyncio.create_task(_orchestration_loop(), name="orchestration"),
            asyncio.create_task(_heartbeat_loop(), name="heartbeat"),
        ]
    except Exception as e:
        log.error(f"Kafka startup failed: {e}")

    AGENT_STATUS_GAUGE.set(1)
    log.info(f"{AGENT_NAME} ready")
    yield

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    try:
        if 'consumer' in locals():
            await consumer.stop()
    except Exception:
        pass
    try:
        if _producer:
            await _producer.stop()
    except Exception:
        pass
    try:
        await disconnect_db()
    except Exception:
        pass
    try:
        await disconnect_redis()
    except Exception:
        pass
    AGENT_STATUS_GAUGE.set(0)


app = FastAPI(title="NITCC Orchestrator Agent", version="1.0.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent": AGENT_NAME,
        "uptime_s": round(time.time() - _start_time, 1),
        "langgraph": "active" if _state_machine and _state_machine._graph else "fallback",
    }


@app.post("/orchestrate/now")
async def trigger_orchestration():
    """Manually trigger an orchestration cycle (admin use)."""
    if not _state_machine:
        return {"error": "State machine not initialized"}
    asyncio.create_task(_state_machine.run_orchestration_cycle([]))
    return {"triggered": True, "timestamp": datetime.utcnow().isoformat()}


@app.put("/config/human-checkpoints")
async def configure_checkpoints(nodes: list[str]):
    """FR-01.3: Configure human-in-the-loop checkpoint nodes."""
    if _state_machine:
        _state_machine.configure_human_checkpoints(nodes)
    return {"configured": True, "nodes": nodes}
