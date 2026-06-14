
"""
Cargo Router — FR-08
GET /cargo/wagons
POST /cargo/routes/recommend
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
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