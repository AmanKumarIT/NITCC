"""
WeatherMind Agent — Main FastAPI Microservice
Domain: Meteorological Intelligence
PRD FR-05
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

from .data_ingestor import WeatherDataIngestor
from .impact_modeler import WeatherImpactModeler

log = structlog.get_logger()
AGENT_ID = "weathermind-agent"
AGENT_NAME = "WeatherMind Agent"

INGESTIONS_TOTAL = Counter("nitcc_weathermind_ingestions_total", "Weather API ingestions")
ADVISORIES_ISSUED = Counter("nitcc_weathermind_advisories_total", "Weather advisories issued")
ERROR_RATE = Counter("nitcc_weathermind_errors_total", "Errors")
AGENT_STATUS_GAUGE = Gauge("nitcc_weathermind_status", "Agent status")

_ingestor: WeatherDataIngestor = None
_impact_modeler: WeatherImpactModeler = None
_producer: NitccKafkaProducer = None
_start_time: float = 0.0


async def _ingest_loop():
    """Ingest weather data every 15 minutes (FR-05.1)."""
    while True:
        try:
            await _ingestor.ingest_all_waypoints()
            INGESTIONS_TOTAL.inc()
            imd_warnings = await _ingestor.fetch_imd_warnings()
            if imd_warnings:
                log.info(f"IMD warnings fetched: {len(imd_warnings)}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            log.error("Weather ingestion error", error=str(e))
        await asyncio.sleep(15 * 60)  # 15 minutes


async def _impact_modeling_loop():
    """Run weather impact assessment after each ingestion (FR-05.2)."""
    while True:
        try:
            advisories = await _impact_modeler.assess_impact_and_generate_advisories(_producer)
            if advisories:
                ADVISORIES_ISSUED.inc(len(advisories))
        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            log.error("Impact modeling error", error=str(e))
        await asyncio.sleep(15 * 60)


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
    global _ingestor, _impact_modeler, _producer, _start_time
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

    _ingestor = WeatherDataIngestor()
    _impact_modeler = WeatherImpactModeler()
    tasks = []
    try:
        _producer = NitccKafkaProducer(settings.kafka_bootstrap_servers, AGENT_ID)
        await _producer.start()
        tasks = [
            asyncio.create_task(_ingest_loop(), name="ingest"),
            asyncio.create_task(_impact_modeling_loop(), name="impact"),
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
        if _ingestor:
            await _ingestor.close()
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


app = FastAPI(title="NITCC WeatherMind Agent", version="1.0.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME, "uptime_s": round(time.time() - _start_time, 1)}


@app.post("/config/reload")
async def config_reload(thresholds: dict):
    if _impact_modeler:
        _impact_modeler.update_thresholds(thresholds.get("thresholds", {}))
    return {"reloaded": True}
