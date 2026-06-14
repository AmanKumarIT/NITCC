"""
NITCC Async MongoDB Client (Motor)
Provides collection access and index initialization for all 9 collections.
"""

from __future__ import annotations
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING, GEOSPHERE
from typing import Optional

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_db(uri: str, db_name: str) -> None:
    """Initialize the MongoDB Atlas connection."""
    global _client, _db
    _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=10000)
    _db = _client[db_name]
    # Verify connectivity
    await _client.admin.command("ping")
    logger.info(f"Connected to MongoDB Atlas — database: {db_name}")
    await _create_indexes()


async def disconnect_db() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not connected. Call connect_db() first.")
    return _db


# ─────────────────────────────────────────────────────────────────────────────
# Collection Accessors
# ─────────────────────────────────────────────────────────────────────────────

def trains_col():
    return get_db()["trains"]

def track_segments_col():
    return get_db()["track_segments"]

def alerts_col():
    return get_db()["alerts"]

def incidents_col():
    return get_db()["incidents"]

def weather_readings_col():
    return get_db()["weather_readings"]

def satellite_risk_zones_col():
    return get_db()["satellite_risk_zones"]

def cargo_wagons_col():
    return get_db()["cargo_wagons"]

def users_col():
    return get_db()["users"]

def agent_state_col():
    return get_db()["agent_state"]

def work_orders_col():
    return get_db()["work_orders"]

def reports_col():
    return get_db()["reports"]

def audit_logs_col():
    return get_db()["audit_logs"]


# ─────────────────────────────────────────────────────────────────────────────
# Index Initialization (PRD Section 12.1 — all GeoJSON 2dsphere + compound)
# ─────────────────────────────────────────────────────────────────────────────

async def _create_indexes() -> None:
    db = get_db()

    # trains
    await db["trains"].create_indexes([
        IndexModel([("trainId", ASCENDING)], unique=True),
        IndexModel([("currentPosition", GEOSPHERE)]),
        IndexModel([("corridorId", ASCENDING)]),
        IndexModel([("riskScore", DESCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("lastUpdated", DESCENDING)]),
    ])

    # track_segments
    await db["track_segments"].create_indexes([
        IndexModel([("segmentId", ASCENDING)], unique=True),
        IndexModel([("geometry", GEOSPHERE)]),
        IndexModel([("healthScore", ASCENDING)]),
        IndexModel([("failureProbability", DESCENDING)]),
        IndexModel([("updatedAt", DESCENDING)]),
    ])

    # alerts
    await db["alerts"].create_indexes([
        IndexModel([("alertId", ASCENDING)], unique=True),
        IndexModel([("domain", ASCENDING), ("severity", ASCENDING)]),
        IndexModel([("severity", ASCENDING)]),
        IndexModel([("createdAt", DESCENDING)]),
        IndexModel([("trainId", ASCENDING)]),
        IndexModel([("segmentId", ASCENDING)]),
        # Alert deduplication: ensure efficient lookup by message hash
        IndexModel([("dismissedAt", ASCENDING)]),
    ])

    # incidents
    await db["incidents"].create_indexes([
        IndexModel([("incidentId", ASCENDING)], unique=True),
        IndexModel([("location", GEOSPHERE)]),
        IndexModel([("severity", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("createdAt", DESCENDING)]),
    ])

    # weather_readings
    await db["weather_readings"].create_indexes([
        IndexModel([("readingId", ASCENDING)], unique=True),
        IndexModel([("waypoint", GEOSPHERE)]),
        IndexModel([("corridorId", ASCENDING)]),
        IndexModel([("forecastedAt", DESCENDING)]),
    ])

    # satellite_risk_zones
    await db["satellite_risk_zones"].create_indexes([
        IndexModel([("zoneId", ASCENDING)], unique=True),
        IndexModel([("geometry", GEOSPHERE)]),
        IndexModel([("riskTier", ASCENDING)]),
        IndexModel([("riskType", ASCENDING)]),
        IndexModel([("analysisDate", DESCENDING)]),
        IndexModel([("changeDetected", ASCENDING)]),
    ])

    # cargo_wagons
    await db["cargo_wagons"].create_indexes([
        IndexModel([("wagonId", ASCENDING)], unique=True),
        IndexModel([("currentPosition", GEOSPHERE)]),
        IndexModel([("trainId", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("updatedAt", DESCENDING)]),
    ])

    # users
    await db["users"].create_indexes([
        IndexModel([("userId", ASCENDING)], unique=True),
        IndexModel([("email", ASCENDING)], unique=True),
        IndexModel([("roles", ASCENDING)]),
    ])

    # agent_state
    await db["agent_state"].create_indexes([
        IndexModel([("agentId", ASCENDING)], unique=True),
        IndexModel([("lastHeartbeat", DESCENDING)]),
        IndexModel([("status", ASCENDING)]),
    ])

    # audit_logs — WORM (never deletable by app layer)
    await db["audit_logs"].create_indexes([
        IndexModel([("userId", ASCENDING)]),
        IndexModel([("action", ASCENDING)]),
        IndexModel([("timestamp", DESCENDING)]),
    ])

    logger.info("MongoDB indexes created successfully")
