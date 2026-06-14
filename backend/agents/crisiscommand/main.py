"""
CrisisCommand Agent — Main FastAPI Microservice
Domain: Emergency Response & Incident Management
PRD FR-06
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
from shared.mongodb import connect_db, disconnect_db, incidents_col
from shared.redis_client import connect_redis, disconnect_redis, set_agent_state
from shared.kafka_client import NitccKafkaProducer, NitccKafkaConsumer, KafkaTopic
from shared.schemas.models import AgentStatus

from .action_plan_generator import ActionPlanGenerator

log = structlog.get_logger()
AGENT_ID = "crisiscommand-agent"
AGENT_NAME = "CrisisCommand Agent"

PLANS_GENERATED = Counter("nitcc_crisis_plans_total", "Action plans generated")
PLANS_TIMEOUT = Counter("nitcc_crisis_plans_timeout_total", "Action plan timeouts")
ERROR_RATE = Counter("nitcc_crisis_plans_errors_total", "Errors")
PLAN_LATENCY = Histogram("nitcc_crisis_plan_latency_seconds", "Action plan generation latency")
AGENT_STATUS_GAUGE = Gauge("nitcc_crisis_status", "Agent status")

_generator: ActionPlanGenerator = None
_producer: NitccKafkaProducer = None
_start_time: float = 0.0


async def _kafka_event_handler(event: dict) -> None:
    """Process emergency domain events."""
    event_type = event.get("eventType", "")
    payload = event.get("payload", {})

    if event_type in ("INCIDENT_DETECTED", "INCIDENT_DECLARED", "INCIDENT_ESCALATED"):
        incident_id = payload.get("incidentId")
        if incident_id:
            await _generate_plan_for_incident(incident_id)


async def _generate_plan_for_incident(incident_id: str) -> None:
    """Generate action plan for a single incident within 60s SLA (FR-06.2)."""
    incident = await incidents_col().find_one({"incidentId": incident_id})
    if not incident:
        log.warning("Incident not found for plan generation", incident_id=incident_id)
        return

    if incident.get("actionPlan"):
        log.debug("Action plan already exists", incident_id=incident_id)
        return

    log.info("Generating action plan", incident_id=incident_id)
    start = time.time()

    try:
        plan = await _generator.generate_action_plan(incident)
        await _generator.update_incident_with_plan(incident_id, plan)
        elapsed = time.time() - start
        PLAN_LATENCY.observe(elapsed)
        PLANS_GENERATED.inc()
        log.info("Action plan generated", incident_id=incident_id, elapsed_s=round(elapsed, 2))

        # Publish to Kafka so orchestrator knows plan is ready
        await _producer.publish(
            topic=KafkaTopic.EMERGENCY,
            event_type="ACTION_PLAN_READY",
            payload={"incidentId": incident_id, "elapsed_s": round(elapsed, 2)},
            domain="emergency",
        )
    except Exception as e:
        ERROR_RATE.inc()
        log.error("Plan generation failed", incident_id=incident_id, error=str(e))


async def _pending_incidents_loop():
    """Poll for incidents without action plans and generate them (FR-06.2)."""
    while True:
        try:
            cursor = incidents_col().find({
                "actionPlan": None,
                "status": {"$ne": "resolved"},
            })
            async for incident in cursor:
                await _generate_plan_for_incident(incident["incidentId"])
        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            log.error("Pending incidents loop error", error=str(e))
        await asyncio.sleep(10)  # Check every 10 seconds


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
    global _generator, _producer, _start_time
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

    _generator = ActionPlanGenerator()
    try:
        await _generator.initialize()
    except Exception as e:
        log.error(f"ActionPlanGenerator initialization failed: {e}")

    tasks = []
    try:
        _producer = NitccKafkaProducer(settings.kafka_bootstrap_servers, AGENT_ID)
        await _producer.start()

        consumer = NitccKafkaConsumer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            agent_id=AGENT_ID,
            topics=[KafkaTopic.EMERGENCY],
            handler=_kafka_event_handler,
        )
        await consumer.start()

        tasks = [
            asyncio.create_task(consumer.consume(), name="kafka_consume"),
            asyncio.create_task(_pending_incidents_loop(), name="pending_check"),
            asyncio.create_task(_heartbeat_loop(), name="heartbeat"),
        ]
    except Exception as e:
        log.error(f"Kafka startup failed: {e}")

    AGENT_STATUS_GAUGE.set(1)
    log.info(f"{AGENT_NAME} ready — LLM: {settings.llm_provider}/{settings.llm_model}")
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


app = FastAPI(title="NITCC CrisisCommand Agent", version="1.0.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME, "uptime_s": round(time.time() - _start_time, 1),
            "llm": f"{settings.llm_provider}/{settings.llm_model}"}
