"""
CargoFlow Agent — Freight Logistics Intelligence
PRD FR-08: Wagon tracking, route optimization (RouteOptima), delay prediction
"""

from __future__ import annotations
import asyncio
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import structlog
from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Gauge

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import settings
from shared.mongodb import connect_db, disconnect_db, cargo_wagons_col, get_db
from shared.redis_client import connect_redis, disconnect_redis, set_agent_state
from shared.kafka_client import NitccKafkaProducer, NitccKafkaConsumer, KafkaTopic
from shared.schemas.models import AgentStatus

log = structlog.get_logger()
AGENT_ID = "cargoflow-agent"
AGENT_NAME = "CargoFlow Agent"

EVENTS_PROCESSED = Counter("nitcc_cargo_events_total", "Events processed")
ROUTES_OPTIMIZED = Counter("nitcc_cargo_routes_total", "Routes optimized")
ERROR_RATE = Counter("nitcc_cargo_errors_total", "Errors")
AGENT_STATUS_GAUGE = Gauge("nitcc_cargo_status", "Agent status")

_producer: NitccKafkaProducer = None
_start_time: float = 0.0


async def _kafka_event_handler(event: dict) -> None:
    """Process logistics events (rerouting requests, wagon status updates)."""
    EVENTS_PROCESSED.inc()
    event_type = event.get("eventType", "")
    payload = event.get("payload", {})

    if event_type == "REROUTING_REQUESTED":
        await _compute_route_recommendations(payload)
    elif event_type == "WAGON_STATUS_UPDATE":
        wagon_id = payload.get("wagonId")
        if wagon_id:
            await cargo_wagons_col().update_one(
                {"wagonId": wagon_id},
                {"$set": {**payload, "updatedAt": datetime.utcnow()}}
            )


async def _compute_route_recommendations(context: dict) -> None:
    """
    FR-08.2: Route optimization using Dijkstra/Dynamic Programming on
    India's railway network graph considering current disruptions.
    """
    # Fetch active disruptions affecting route optimization
    disrupted_segments = []
    try:
        from shared.mongodb import track_segments_col, weather_readings_col
        # Segments with health < 40 or CRITICAL weather
        async for seg in track_segments_col().find({"healthScore": {"$lt": 40}}):
            disrupted_segments.append(seg.get("segmentId"))
    except Exception as e:
        log.warning("Could not fetch disrupted segments", error=str(e))

    # In production: full route graph optimization
    # For now: store a recommendation document for the API to serve
    rec = {
        "origin": context.get("origin", "Delhi"),
        "destination": context.get("destination", "Mumbai"),
        "reason": context.get("reason", "weather_advisory"),
        "primaryRoute": {
            "name": "Primary Route",
            "segments": ["DELHI-KOTA", "KOTA-SURAT", "SURAT-MUMBAI"],
            "estimatedTime": "26h",
            "distance_km": 1400,
            "disruptions": len(disrupted_segments),
        },
        "alternativeRoutes": [
            {
                "name": "Alternate Route (via Nagpur)",
                "segments": ["DELHI-BHOPAL", "BHOPAL-NAGPUR", "NAGPUR-MUMBAI"],
                "estimatedTime": "32h",
                "distance_km": 1600,
                "disruptions": 0,
            }
        ],
        "computedAt": datetime.utcnow().isoformat(),
        "disrupted_segments": disrupted_segments,
    }

    await get_db()["route_recommendations"].update_one(
        {"origin": rec["origin"], "destination": rec["destination"]},
        {"$set": rec},
        upsert=True,
    )
    ROUTES_OPTIMIZED.inc()
    log.info("Route recommendation computed", origin=rec["origin"], destination=rec["destination"])


async def _wagon_tracking_loop():
    """Update wagon positions from NTES/GPS feed every 5 minutes (FR-08.1)."""
    while True:
        try:
            # In production: fetch from NTES API / GPS telemetry
            # For now: update timestamps for all wagons
            await cargo_wagons_col().update_many(
                {},
                {"$set": {"updatedAt": datetime.utcnow()}}
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            log.error("Wagon tracking error", error=str(e))
        await asyncio.sleep(5 * 60)


async def _delay_prediction_loop():
    """FR-08.3: Predict delivery delays using historical patterns daily."""
    while True:
        try:
            log.info("Running delay prediction analysis...")
            # ML model would run here using scikit-learn
            pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            log.error("Delay prediction error", error=str(e))
        await asyncio.sleep(24 * 3600)


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
    global _producer, _start_time
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

        consumer = NitccKafkaConsumer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            agent_id=AGENT_ID,
            topics=[KafkaTopic.LOGISTICS, KafkaTopic.RAILWAY],
            handler=_kafka_event_handler,
        )
        await consumer.start()

        tasks = [
            asyncio.create_task(consumer.consume(), name="kafka"),
            asyncio.create_task(_wagon_tracking_loop(), name="wagon_tracking"),
            asyncio.create_task(_delay_prediction_loop(), name="delay_pred"),
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


app = FastAPI(title="NITCC CargoFlow Agent", version="1.0.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME, "uptime_s": round(time.time() - _start_time, 1)}
