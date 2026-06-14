"""
Weather Router — FR-05
GET /weather/corridors
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
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