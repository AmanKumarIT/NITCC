"""
Trains Router
GET /trains — List all active trains with position, speed, risk score
GET /trains/{id}/telemetry — Live telemetry stream (SSE)
"""

from __future__ import annotations
import asyncio
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.mongodb import trains_col
from shared.auth import get_current_user, CurrentUser
from shared.schemas.models import APIResponse, PaginatedResponse

router = APIRouter()


@router.get("", summary="List all active trains")
async def list_trains(
    corridor_id: Optional[str] = Query(None),
    min_risk: Optional[float] = Query(None, ge=0, le=100),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Returns all active trains with position, speed, and risk score.
    Operators see only their jurisdiction zones.
    SLA: <300ms (p99) — PRD Section 8.1
    """
    query: dict = {}
    if corridor_id:
        query["corridorId"] = corridor_id
    if min_risk is not None:
        query["riskScore"] = {"$gte": min_risk}
    if status:
        query["status"] = status

    # Jurisdiction zone filter for Operator role
    if not user.has_role(__import__('shared.schemas.models', fromlist=['UserRole']).UserRole.SUPERVISOR):
        if user.jurisdiction_zones:
            query["corridorId"] = {"$in": user.jurisdiction_zones}

    skip = (page - 1) * page_size
    cursor = trains_col().find(query, {"_id": 0}).sort("riskScore", -1).skip(skip).limit(page_size)
    trains = await cursor.to_list(length=page_size)
    total = await trains_col().count_documents(query)

    return PaginatedResponse(data=trains, total=total, page=page, page_size=page_size)


@router.get("/{train_id}/telemetry", summary="Live telemetry stream for a specific train (SSE)")
async def train_telemetry_sse(
    train_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Server-Sent Events stream for real-time train telemetry.
    Sends updates every 60 seconds (risk score update interval per FR-02.2).
    """
    async def event_stream():
        while True:
            doc = await trains_col().find_one({"trainId": train_id}, {"_id": 0})
            if doc:
                data = json.dumps(doc, default=str)
                yield f"data: {data}\n\n"
            else:
                yield f"data: {json.dumps({'error': 'Train not found'})}\n\n"
            await asyncio.sleep(5)  # Poll every 5s for live feel; agents update every 60s

    return StreamingResponse(event_stream(), media_type="text/event-stream")
