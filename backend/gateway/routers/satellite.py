"""
Satellite Router — FR-04
GET /satellite/risk-zones
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
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