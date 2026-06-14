"""
TrackWatch Agent — Main FastAPI Microservice
Domain: Railway Infrastructure
PRD FR-02.1, FR-02.2, FR-07

Responsibilities:
- Track health scoring (composite, every 6 hours)
- Accident risk index per train (every 60 seconds)
- Track failure prediction (ML model daily)
- Work order generation
- Kafka consumer: nitcc.railway.events
- Kafka producer: nitcc.railway.events (health score events)
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
from shared.mongodb import connect_db, disconnect_db, track_segments_col, trains_col
from shared.redis_client import connect_redis, disconnect_redis, set_agent_state
from shared.kafka_client import NitccKafkaProducer, NitccKafkaConsumer, KafkaTopic
from shared.schemas.models import AgentStatus, AgentMetricsSnapshot

from .health_scoring import TrackHealthScorer
from .risk_scoring import AccidentRiskScorer
from .ml_inference import TrackFailurePredictor
from .work_order import WorkOrderGenerator

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

AGENT_ID = "trackwatch-agent"
AGENT_NAME = "TrackWatch Agent"

# Prometheus metrics (Appendix A: GET /metrics)
EVENTS_PROCESSED = Counter("nitcc_trackwatch_events_total", "Events processed")
INFERENCE_DURATION = Histogram("nitcc_trackwatch_inference_duration_seconds", "ML inference latency")
ERROR_RATE = Counter("nitcc_trackwatch_errors_total", "Error count")
AGENT_STATUS_GAUGE = Gauge("nitcc_trackwatch_status", "Agent status (1=running, 0=error)")

# ─────────────────────────────────────────────────────────────────────────────
# Core services
# ─────────────────────────────────────────────────────────────────────────────
_health_scorer: TrackHealthScorer = None
_risk_scorer: AccidentRiskScorer = None
_predictor: TrackFailurePredictor = None
_work_order_gen: WorkOrderGenerator = None
_producer: NitccKafkaProducer = None
_start_time: float = 0.0


async def _kafka_event_handler(event: dict) -> None:
    """Process incoming Kafka events from railway domain."""
    EVENTS_PROCESSED.inc()
    event_type = event.get("eventType", "")
    payload = event.get("payload", {})

    try:
        if event_type == "TELEMETRY_UPDATE":
            # Update risk score for this train
            train_id = payload.get("trainId")
            if train_id:
                await _risk_scorer.update_train_risk(train_id, payload)

        elif event_type == "SENSOR_READING":
            # Update track health for segment
            segment_id = payload.get("segmentId")
            if segment_id:
                await _health_scorer.process_sensor_reading(segment_id, payload)

    except Exception as e:
        ERROR_RATE.inc()
        log.error("Error handling Kafka event", event_type=event_type, error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _health_scorer, _risk_scorer, _predictor, _work_order_gen, _producer, _start_time
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

    _health_scorer = TrackHealthScorer()
    _risk_scorer = AccidentRiskScorer()
    _predictor = TrackFailurePredictor()
    _work_order_gen = WorkOrderGenerator()

    # Load ML model
    try:
        await _predictor.load_model()
    except Exception as e:
        log.error(f"ML model load failed: {e}")

    # Start Kafka producer
    tasks = []
    try:
        _producer = NitccKafkaProducer(settings.kafka_bootstrap_servers, AGENT_ID)
        await _producer.start()

        # Start Kafka consumer in background
        consumer = NitccKafkaConsumer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            agent_id=AGENT_ID,
            topics=[KafkaTopic.RAILWAY],
            handler=_kafka_event_handler,
        )
        await consumer.start()

        # Background tasks
        tasks = [
            asyncio.create_task(consumer.consume(), name="kafka_consume"),
            asyncio.create_task(_health_score_loop(), name="health_score_loop"),
            asyncio.create_task(_risk_score_loop(), name="risk_score_loop"),
            asyncio.create_task(_heartbeat_loop(), name="heartbeat"),
        ]
    except Exception as e:
        log.error(f"Kafka startup failed: {e}")

    AGENT_STATUS_GAUGE.set(1)
    log.info(f"{AGENT_NAME} ready")
    yield

    # Cleanup
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
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
    log.info(f"{AGENT_NAME} shut down")


async def _health_score_loop():
    """Compute and store track health scores every 6 hours (FR-07.1)."""
    while True:
        try:
            log.info("Starting track health scoring cycle...")
            await _health_scorer.score_all_segments(_predictor, _producer, _work_order_gen)
            log.info("Track health scoring cycle complete")
        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            log.error("Health scoring error", error=str(e))
        await asyncio.sleep(6 * 3600)  # 6 hours


async def _risk_score_loop():
    """Update risk scores for all trains in motion every 60 seconds (FR-02.2)."""
    while True:
        try:
            await _risk_scorer.score_all_active_trains(_producer)
        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            log.error("Risk scoring error", error=str(e))
        await asyncio.sleep(60)  # 60 seconds


async def _heartbeat_loop():
    """Update agent state in Redis every 30 seconds (Appendix A monitoring)."""
    while True:
        try:
            uptime = time.time() - _start_time
            state = {
                "agentId": AGENT_ID,
                "agentName": AGENT_NAME,
                "status": AgentStatus.RUNNING.value,
                "lastHeartbeat": datetime.utcnow().isoformat(),
                "uptime_s": round(uptime, 1),
                "metricsSnapshot": {
                    "events_processed_total": int(EVENTS_PROCESSED._value.get()),
                    "error_rate": float(ERROR_RATE._value.get()),
                },
            }
            await set_agent_state(AGENT_ID, state)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning("Heartbeat error", error=str(e))
        await asyncio.sleep(30)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NITCC TrackWatch Agent",
    description="Railway Infrastructure Monitoring Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Prometheus metrics
app.mount("/metrics", make_asgi_app())


@app.get("/health", summary="Agent health check (Appendix A)")
async def health():
    """Returns { status: 'ok'|'degraded'|'error', uptime_s, last_event_at }"""
    uptime = time.time() - _start_time if _start_time else 0
    return {
        "status": "ok",
        "agent": AGENT_NAME,
        "uptime_s": round(uptime, 1),
        "last_event_at": datetime.utcnow().isoformat(),
    }


@app.post("/config/reload", summary="Hot config reload (FR-01.1)")
async def config_reload(thresholds: dict):
    """
    FR-01.1: Support hot configuration reload without restart.
    Accepts { thresholds: {...} } and reloads scoring thresholds.
    """
    if _health_scorer:
        _health_scorer.update_thresholds(thresholds.get("thresholds", {}))
    if _risk_scorer:
        _risk_scorer.update_thresholds(thresholds.get("thresholds", {}))

    return {"reloaded": True, "diff": thresholds}
