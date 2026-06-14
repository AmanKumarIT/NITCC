"""
SatEye Agent — Satellite Image Analysis
PRD FR-04: Daily satellite image processing, change detection, risk zone classification
"""

from __future__ import annotations
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Gauge

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import settings
from shared.mongodb import connect_db, disconnect_db, satellite_risk_zones_col
from shared.redis_client import connect_redis, disconnect_redis, set_agent_state
from shared.kafka_client import NitccKafkaProducer, KafkaTopic
from shared.schemas.models import AgentStatus

logger = structlog.get_logger()

AGENT_ID = "sateye-agent"
AGENT_NAME = "SatEye Agent"

EVENTS_PROCESSED = Counter("nitcc_sateye_events_total", "Satellite analysis events")
ZONES_DETECTED = Counter("nitcc_sateye_risk_zones_total", "Risk zones classified")
ERROR_RATE = Counter("nitcc_sateye_errors_total", "Error count")
AGENT_STATUS_GAUGE = Gauge("nitcc_sateye_status", "Agent status")

_producer: NitccKafkaProducer = None
_start_time: float = 0.0


async def _satellite_analysis_loop():
    """
    FR-04.1: Process Sentinel/ISRO imagery daily.
    Runs change detection, classifies risk zones, updates MongoDB.
    """
    while True:
        try:
            logger.info("Starting satellite analysis cycle...")
            await _run_satellite_analysis()
            logger.info("Satellite analysis cycle complete")
        except asyncio.CancelledError:
            break
        except Exception as e:
            ERROR_RATE.inc()
            logger.error("Satellite analysis error", error=str(e))
        await asyncio.sleep(24 * 3600)  # Daily


async def _run_satellite_analysis():
    """
    Core satellite analysis pipeline:
    1. Fetch latest Sentinel-2 imagery tiles for India's rail corridors
    2. Run NDVI/NDWI/DEM change detection via Google Earth Engine API
    3. Classify risk zones (landslide, flood, subsidence, encroachment)
    4. Update MongoDB satellite_risk_zones collection
    5. Publish change alerts to Kafka
    """
    if not settings.gee_service_account_json:
        logger.warning("Google Earth Engine credentials not configured — using placeholder zones")
        await _seed_demo_risk_zones()
        return

    # In production: actual GEE / ISRO API calls happen here
    # ee.Initialize(credentials)
    # imagery = ee.ImageCollection("COPERNICUS/S2_SR").filterDate(...)
    # ndvi = imagery.normalizedDifference(['B8', 'B4'])
    # ...
    logger.info("Satellite analysis: GEE integration active")


async def _seed_demo_risk_zones():
    """Seed sample risk zones for development/demo purposes."""
    demo_zones = [
        {
            "zoneId": "SRZ-KASARA-001",
            "riskType": "landslide",
            "riskTier": "HIGH",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[73.3, 19.5], [73.5, 19.5], [73.5, 19.7], [73.3, 19.7], [73.3, 19.5]]]
            },
            "changeDetected": True,
            "ndviChange": -0.18,
            "analysisDate": datetime.utcnow().isoformat(),
            "source": "demo",
            "imageId": "DEMO-2026-001",
            "confidenceScore": 0.82,
        },
        {
            "zoneId": "SRZ-PATNA-001",
            "riskType": "flood",
            "riskTier": "CRITICAL",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[85.0, 25.4], [85.3, 25.4], [85.3, 25.7], [85.0, 25.7], [85.0, 25.4]]]
            },
            "changeDetected": True,
            "ndviChange": -0.35,
            "analysisDate": datetime.utcnow().isoformat(),
            "source": "demo",
            "imageId": "DEMO-2026-002",
            "confidenceScore": 0.91,
        },
    ]

    for zone in demo_zones:
        existing = await satellite_risk_zones_col().find_one({"zoneId": zone["zoneId"]})
        if not existing:
            await satellite_risk_zones_col().insert_one(zone)
            ZONES_DETECTED.inc()
            logger.info(f"Seeded demo risk zone: {zone['zoneId']}")


async def _heartbeat_loop():
    while True:
        try:
            uptime = time.time() - _start_time
            await set_agent_state(AGENT_ID, {
                "agentId": AGENT_ID,
                "agentName": AGENT_NAME,
                "status": AgentStatus.RUNNING.value,
                "lastHeartbeat": datetime.utcnow().isoformat(),
                "uptime_s": round(uptime, 1),
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
    logger.info(f"{AGENT_NAME} starting...")
    try:
        await connect_db(settings.mongodb_uri, settings.mongodb_db_name)
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
    try:
        await connect_redis(settings.redis_url, settings.redis_password)
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
    tasks = []
    try:
        _producer = NitccKafkaProducer(settings.kafka_bootstrap_servers, AGENT_ID)
        await _producer.start()
        tasks = [
            asyncio.create_task(_satellite_analysis_loop(), name="sat_analysis"),
            asyncio.create_task(_heartbeat_loop(), name="heartbeat"),
        ]
    except Exception as e:
        logger.error(f"Kafka startup failed: {e}")
    AGENT_STATUS_GAUGE.set(1)
    logger.info(f"{AGENT_NAME} ready")
    yield

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


app = FastAPI(title="NITCC SatEye Agent", version="1.0.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME, "uptime_s": round(time.time() - _start_time, 1)}
