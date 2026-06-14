"""
Remaining Gateway Routers (tracks, weather, satellite, cargo, agents, reports)
"""

# ── tracks.py ──────────────────────────────────────────────────────────────
TRACKS_CONTENT = '''"""
Track Health Router — FR-07
GET /tracks
GET /tracks/{segmentId}/history
POST /tracks/{segmentId}/work-orders
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
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
'''

# ── weather.py ─────────────────────────────────────────────────────────────
WEATHER_CONTENT = '''"""
Weather Router — FR-05
GET /weather/corridors
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared.mongodb import weather_readings_col
from shared.auth import get_current_user, CurrentUser
from shared.schemas.models import APIResponse, PaginatedResponse

router = APIRouter()

@router.get("/corridors", summary="Current weather data and forecasts per corridor")
async def weather_corridors(
    corridor_id: Optional[str] = Query(None),
    impact_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
):
    """Returns latest weather readings per corridor waypoint (updated every 15 min)."""
    query: dict = {}
    if corridor_id:
        query["corridorId"] = corridor_id
    if impact_code:
        query["impactCode"] = impact_code

    skip = (page - 1) * page_size
    cursor = weather_readings_col().find(query, {"_id": 0}).sort("forecastedAt", -1).skip(skip).limit(page_size)
    items = await cursor.to_list(length=page_size)
    total = await weather_readings_col().count_documents(query)
    return PaginatedResponse(data=items, total=total, page=page, page_size=page_size)
'''

# ── satellite.py ───────────────────────────────────────────────────────────
SATELLITE_CONTENT = '''"""
Satellite Router — FR-04
GET /satellite/risk-zones
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared.mongodb import satellite_risk_zones_col
from shared.auth import get_current_user, CurrentUser
from shared.schemas.models import APIResponse, PaginatedResponse, RiskTier, SatelliteRiskType

router = APIRouter()

@router.get("/risk-zones", summary="GeoJSON risk zones from latest satellite analysis")
async def satellite_risk_zones(
    risk_tier: Optional[RiskTier] = Query(None),
    risk_type: Optional[SatelliteRiskType] = Query(None),
    change_detected: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
):
    """Returns GeoJSON polygon risk zones classified by SatEye Agent daily."""
    query: dict = {}
    if risk_tier:
        query["riskTier"] = risk_tier.value
    if risk_type:
        query["riskType"] = risk_type.value
    if change_detected is not None:
        query["changeDetected"] = change_detected

    skip = (page - 1) * page_size
    cursor = satellite_risk_zones_col().find(query, {"_id": 0}).sort("analysisDate", -1).skip(skip).limit(page_size)
    items = await cursor.to_list(length=page_size)
    total = await satellite_risk_zones_col().count_documents(query)

    # Return as GeoJSON FeatureCollection for Mapbox direct consumption
    features = [
        {
            "type": "Feature",
            "geometry": item.get("geometry"),
            "properties": {k: v for k, v in item.items() if k != "geometry"},
        }
        for item in items
    ]
    geojson = {"type": "FeatureCollection", "features": features}
    return APIResponse(data=geojson)
'''

# ── cargo.py ───────────────────────────────────────────────────────────────
CARGO_CONTENT = '''"""
Cargo Router — FR-08
GET /cargo/wagons
POST /cargo/routes/recommend
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared.mongodb import cargo_wagons_col
from shared.auth import get_current_user, require_operator, CurrentUser
from shared.schemas.models import APIResponse, PaginatedResponse, CargoWagonStatus

router = APIRouter()

class RouteRecommendRequest(BaseModel):
    origin: str
    destination: str
    cargo_type: str
    cargo_weight_tons: float
    priority: str = "standard"  # standard | express | economy

@router.get("/wagons", summary="Active freight wagons with location and status")
async def list_wagons(
    status: Optional[CargoWagonStatus] = Query(None),
    train_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
):
    query: dict = {}
    if status:
        query["status"] = status.value
    if train_id:
        query["trainId"] = train_id

    skip = (page - 1) * page_size
    cursor = cargo_wagons_col().find(query, {"_id": 0}).sort("updatedAt", -1).skip(skip).limit(page_size)
    items = await cursor.to_list(length=page_size)
    total = await cargo_wagons_col().count_documents(query)
    return PaginatedResponse(data=items, total=total, page=page, page_size=page_size)

@router.post("/routes/recommend", summary="Route optimization recommendations (FR-08.2)")
async def recommend_routes(
    body: RouteRecommendRequest,
    user: CurrentUser = Depends(require_operator),
):
    """
    Delegates to CargoFlow Agent RouteOptima logic.
    Returns optimal route + alternatives with trade-off summaries.
    This is a synchronous call; CargoFlow Agent pre-computes recommendations.
    """
    # Fetch pre-computed recommendations from MongoDB (written by CargoFlow Agent)
    from shared.mongodb import get_db
    rec = await get_db()["route_recommendations"].find_one(
        {"origin": body.origin, "destination": body.destination},
        {"_id": 0}
    )
    if rec:
        return APIResponse(data=rec)
    return APIResponse(
        message="Route recommendation being computed by CargoFlow Agent. Retry in 30 seconds.",
        data=None
    )
'''

# ── agents_router.py ───────────────────────────────────────────────────────
AGENTS_CONTENT = '''"""
Agents Router — Admin only
GET /agents/status
"""
from fastapi import APIRouter, Depends
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared.redis_client import get_all_agent_states
from shared.mongodb import agent_state_col
from shared.auth import require_admin, CurrentUser
from shared.schemas.models import APIResponse

router = APIRouter()

@router.get("/status", summary="Health and state of all AI agents (Admin only)")
async def agents_status(user: CurrentUser = Depends(require_admin)):
    """
    Returns live state of all 7 NITCC agents from MongoDB + Redis.
    FR-01.1: Each agent exposes /health; orchestrator aggregates here.
    """
    cursor = agent_state_col().find({}, {"_id": 0}).sort("agentName", 1)
    agents = await cursor.to_list(length=20)
    redis_states = await get_all_agent_states()
    
    # Merge Redis real-time state
    for agent in agents:
        agent_id = agent.get("agentId")
        if agent_id in redis_states:
            agent["liveContext"] = redis_states[agent_id]
    
    return APIResponse(data=agents)
'''

# ── reports.py ─────────────────────────────────────────────────────────────
REPORTS_CONTENT = '''"""
Reports Router
POST /reports/generate
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared.mongodb import reports_col
from shared.auth import require_supervisor, CurrentUser
from shared.schemas.models import APIResponse

router = APIRouter()

VALID_REPORT_TYPES = [
    "weekly_risk_summary",
    "weather_briefing",
    "infrastructure_health",
    "cargo_performance",
    "incident_summary",
]

class GenerateReportRequest(BaseModel):
    report_type: str
    zone_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    format: str = "json"  # json | pdf | csv

@router.post("/generate", summary="Trigger report generation", status_code=202)
async def generate_report(
    body: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(require_supervisor),
):
    if body.report_type not in VALID_REPORT_TYPES:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid report type. Valid: {VALID_REPORT_TYPES}")

    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.utcnow()
    
    report_doc = {
        "reportId": report_id,
        "type": body.report_type,
        "requestedBy": user.user_id,
        "status": "queued",
        "format": body.format,
        "parameters": {"zone_id": body.zone_id, "date_from": body.date_from, "date_to": body.date_to},
        "createdAt": now,
        "downloadUrl": None,
    }
    await reports_col().insert_one(report_doc)
    # Background Airflow DAG would pick this up via polling the reports collection
    
    return APIResponse(
        data={"reportId": report_id},
        message=f"Report {report_id} queued for generation. Check /api/v1/reports/{report_id} for status.",
        code=202
    )

@router.get("/{report_id}", summary="Get report status and download URL")
async def get_report(report_id: str, user: CurrentUser = Depends(require_supervisor)):
    report = await reports_col().find_one({"reportId": report_id}, {"_id": 0})
    if not report:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report not found")
    return APIResponse(data=report)
'''

# Write all files
import os

files = {
    "backend/gateway/routers/tracks.py": TRACKS_CONTENT,
    "backend/gateway/routers/weather.py": WEATHER_CONTENT,
    "backend/gateway/routers/satellite.py": SATELLITE_CONTENT,
    "backend/gateway/routers/cargo.py": CARGO_CONTENT,
    "backend/gateway/routers/agents_router.py": AGENTS_CONTENT,
    "backend/gateway/routers/reports.py": REPORTS_CONTENT,
}

for path, content in files.items():
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content.strip())
    print(f"Written: {path}")

print("All gateway routers written!")
