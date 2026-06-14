"""
NITCC Async Redis Client
Implements Appendix A: Agent state key pattern + alert deduplication (FR-03.2)
"""

from __future__ import annotations
import json
import logging
import hashlib
from datetime import datetime
from typing import Optional, Any, Dict
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None

# TTL Constants (seconds)
AGENT_STATE_TTL = 300           # Appendix A: 300s TTL for agent state
ALERT_DEDUP_TTL = 300           # FR-03.2: 5-minute deduplication window
SESSION_TTL = 3600              # JWT refresh session


async def connect_redis(url: str, password: Optional[str] = None) -> None:
    global _redis_client
    _redis_client = aioredis.from_url(
        url,
        password=password or None,
        decode_responses=True,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    await _redis_client.ping()
    logger.info("Connected to Redis")


async def disconnect_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis not connected. Call connect_redis() first.")
    return _redis_client


# ─────────────────────────────────────────────────────────────────────────────
# Agent State Management (Appendix A)
# ─────────────────────────────────────────────────────────────────────────────

async def set_agent_state(agent_id: str, state: Dict[str, Any]) -> None:
    """
    Write agent state to Redis with TTL=300s.
    Key: agent:{agentId}:state (Appendix A contract)
    """
    key = f"agent:{agent_id}:state"
    value = json.dumps(state, default=str)
    await get_redis().setex(key, AGENT_STATE_TTL, value)


async def get_agent_state(agent_id: str) -> Optional[Dict[str, Any]]:
    """Read agent state from Redis."""
    key = f"agent:{agent_id}:state"
    raw = await get_redis().get(key)
    if raw:
        return json.loads(raw)
    return None


async def get_all_agent_states() -> Dict[str, Dict[str, Any]]:
    """Read all agent states (for Orchestrator global belief state)."""
    keys = await get_redis().keys("agent:*:state")
    states = {}
    for key in keys:
        raw = await get_redis().get(key)
        agent_id = key.split(":")[1]
        if raw:
            states[agent_id] = json.loads(raw)
    return states


# ─────────────────────────────────────────────────────────────────────────────
# Alert Deduplication (FR-03.2 — 5-minute suppression window)
# ─────────────────────────────────────────────────────────────────────────────

def _alert_dedup_key(domain: str, severity: str, message: str) -> str:
    content = f"{domain}:{severity}:{message}"
    h = hashlib.md5(content.encode()).hexdigest()
    return f"alert:dedup:{h}"


async def check_and_register_alert(
    domain: str,
    severity: str,
    message: str,
) -> bool:
    """
    Returns True if alert is new (should be stored/sent).
    Returns False if it's a duplicate within the 5-minute window (suppress it).
    """
    key = _alert_dedup_key(domain, severity, message)
    redis = get_redis()
    # NX=True means only set if key doesn't exist
    result = await redis.set(key, "1", ex=ALERT_DEDUP_TTL, nx=True)
    return result is not None  # True = new, None = already exists (suppress)


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Dashboard State (for broadcasting)
# ─────────────────────────────────────────────────────────────────────────────

async def publish_dashboard_event(channel: str, event: Dict[str, Any]) -> None:
    """Publish event to Redis pub/sub for WebSocket broadcast."""
    await get_redis().publish(channel, json.dumps(event, default=str))


# ─────────────────────────────────────────────────────────────────────────────
# National Risk Index Cache
# ─────────────────────────────────────────────────────────────────────────────

async def set_national_risk_index(nri_data: Dict[str, Any]) -> None:
    """Cache National Risk Index updated every 5 minutes."""
    await get_redis().setex("nri:current", 600, json.dumps(nri_data, default=str))


async def get_national_risk_index() -> Optional[Dict[str, Any]]:
    raw = await get_redis().get("nri:current")
    return json.loads(raw) if raw else None


# ─────────────────────────────────────────────────────────────────────────────
# Config Hotload Cache (FR-01.1)
# ─────────────────────────────────────────────────────────────────────────────

async def set_agent_config(agent_id: str, config: Dict[str, Any]) -> None:
    """Store runtime config for hot reload (FR-01.1)."""
    await get_redis().set(
        f"agent:{agent_id}:config", json.dumps(config, default=str)
    )


async def get_agent_config(agent_id: str) -> Optional[Dict[str, Any]]:
    raw = await get_redis().get(f"agent:{agent_id}:config")
    return json.loads(raw) if raw else None
