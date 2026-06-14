"""
WebSocket Router — Real-time Dashboard Event Feed
PRD Section 11.2: WS /ws/dashboard
PRD FR-03.1: sub-second latency WebSocket updates
"""

from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
import redis.asyncio as aioredis

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.redis_client import get_redis
from shared.auth import decode_token
from shared.schemas.models import UserRole

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Connection Manager
# Groups connections by user role and jurisdiction zone for targeted broadcasts
# ─────────────────────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        # websocket → user_info
        self._connections: Dict[WebSocket, dict] = {}

    async def connect(self, ws: WebSocket, user_info: dict) -> None:
        await ws.accept()
        self._connections[ws] = user_info
        logger.info(
            f"WebSocket connected: user={user_info.get('user_id')} "
            f"total_connections={len(self._connections)}"
        )

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.pop(ws, None)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, message: dict, domain: str = "all") -> None:
        """Broadcast event to all connected clients (or filter by domain/zone)."""
        payload = json.dumps(message, default=str)
        dead = []
        for ws, user_info in self._connections.items():
            try:
                # Jurisdiction zone filtering for Operator role
                zones = user_info.get("zones", [])
                event_zone = message.get("payload", {}).get("zone", "national")
                role_level = user_info.get("max_role_level", 0)

                # Supervisor+ sees all zones; Operator sees only their zones
                if role_level >= 2 or event_zone == "national" or event_zone in zones or not zones:
                    await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    async def send_personal(self, ws: WebSocket, message: dict) -> None:
        try:
            await ws.send_text(json.dumps(message, default=str))
        except Exception:
            self.disconnect(ws)


manager = ConnectionManager()


# ─────────────────────────────────────────────────────────────────────────────
# Redis Pub/Sub → WebSocket Bridge
# Subscribes to all nitcc.* channels and forwards to connected clients
# ─────────────────────────────────────────────────────────────────────────────

async def redis_to_ws_bridge():
    """
    Background task: subscribes to Redis pub/sub channels and
    broadcasts events to all connected WebSocket clients.
    """
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.psubscribe("nitcc.*")  # Subscribe to all NITCC channels

    logger.info("Redis→WebSocket bridge started")
    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    data = json.loads(message["data"])
                    domain = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                    data["_channel"] = domain
                    data["_ts"] = datetime.utcnow().isoformat()
                    await manager.broadcast(data)
                except Exception as e:
                    logger.warning(f"WS bridge error: {e}")
    except asyncio.CancelledError:
        await pubsub.punsubscribe("nitcc.*")
        logger.info("Redis→WebSocket bridge stopped")


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/dashboard")
async def dashboard_ws(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    Real-time dashboard event feed.
    Clients connect with a valid JWT token as query param.
    Receives all domain events: railway, weather, satellite, logistics, emergency.
    SLA: <500ms from event generation to client delivery (PRD Section 8.1)
    """
    # Authenticate WebSocket connection
    try:
        payload = decode_token(token)
        user_info = {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
            "zones": payload.get("zones", []),
            "max_role_level": max(
                ({"ReadOnly": 0, "Operator": 1, "Supervisor": 2, "Emergency": 3, "Admin": 4}.get(r, 0)
                 for r in payload.get("roles", [])),
                default=0,
            ),
        }
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user_info)

    # Send initial connection confirmation
    await manager.send_personal(websocket, {
        "type": "connected",
        "message": "NITCC dashboard feed connected",
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_info["user_id"],
    })

    try:
        while True:
            # Keep connection alive + handle ping/pong
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_personal(websocket, {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Export manager for use by other routers to broadcast events
def get_ws_manager() -> ConnectionManager:
    return manager
