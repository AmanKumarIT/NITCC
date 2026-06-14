"""
Track Health Router — FR-07
GET /tracks
GET /tracks/{segmentId}/history
POST /tracks/{segmentId}/work-orders
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from shared.mongodb import track_segments_col, work_orders_col
from shared.auth import get_current_user, require_supervisor, CurrentUser
from shared.schemas.models import PaginatedResponse, APIResponse

router = APIRouter()

@router.get("", summary="List all track segments with health scores")
async def list_tracks(
    min_health: Optional[float] = Query(None, ge=0, le=100),
    max_health: Optional[float] = Query(None, ge=0, le=100),
    from_station: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
):
    query: dict = {}
    health_filter = {}
    if min_health is not None:
        health_filter["$gte"] = min_health
    if max_health is not None:
        health_filter["$lte"] = max_health
    if health_filter:
        query["healthScore"] = health_filter
    if from_station:
        query["fromStation"] = from_station

    skip = (page - 1) * page_size
    cursor = track_segments_col().find(query, {"_id": 0}).sort("healthScore", 1).skip(skip).limit(page_size)
    items = await cursor.to_list(length=page_size)
    total = await track_segments_col().count_documents(query)
    return PaginatedResponse(data=items, total=total, page=page, page_size=page_size)

@router.get("/{segment_id}/history", summary="Health score time-series for a segment")
async def track_history(
    segment_id: str,
    days: int = Query(30, ge=1, le=730),
    user: CurrentUser = Depends(get_current_user),
):
    """Returns health score history (stored by TrackWatch Agent every 6 hours)."""
    from shared.mongodb import get_db
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    cursor = get_db()["track_health_history"].find(
        {"segmentId": segment_id, "recordedAt": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("recordedAt", 1)
    items = await cursor.to_list(length=days * 4)  # 4 readings/day
    return APIResponse(data=items)

@router.get("/{segment_id}/work-orders", summary="List work orders for a segment")
async def list_work_orders(segment_id: str, user: CurrentUser = Depends(require_supervisor)):
    cursor = work_orders_col().find({"segmentId": segment_id}, {"_id": 0}).sort("createdAt", -1)
    items = await cursor.to_list(length=100)
    return APIResponse(data=items)