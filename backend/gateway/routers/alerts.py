"""
Alerts Router — FR-03.2
GET /alerts — Paginated list with severity filter
POST /alerts/{id}/dismiss — Dismiss (authorized roles only)
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.mongodb import alerts_col, audit_logs_col
from shared.auth import get_current_user, CurrentUser, require_operator
from shared.schemas.models import APIResponse, PaginatedResponse, AlertSeverity, AlertDomain

router = APIRouter()


class DismissRequest(BaseModel):
    reason: Optional[str] = None


@router.get("", summary="List active and historical alerts")
async def list_alerts(
    domain: Optional[AlertDomain] = Query(None),
    severity: Optional[AlertSeverity] = Query(None),
    dismissed: Optional[bool] = Query(None),
    train_id: Optional[str] = Query(None),
    segment_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
):
    """All WARN and CRITICAL alerts with timestamps (FR-03.2)."""
    query: dict = {}
    if domain:
        query["domain"] = domain.value
    if severity:
        query["severity"] = severity.value
    if dismissed is not None:
        query["dismissedAt"] = {"$exists": dismissed}
    if train_id:
        query["trainId"] = train_id
    if segment_id:
        query["segmentId"] = segment_id

    skip = (page - 1) * page_size
    cursor = alerts_col().find(query, {"_id": 0}).sort("createdAt", -1).skip(skip).limit(page_size)
    items = await cursor.to_list(length=page_size)
    total = await alerts_col().count_documents(query)

    return PaginatedResponse(data=items, total=total, page=page, page_size=page_size)


@router.post("/{alert_id}/dismiss", summary="Dismiss an alert (Operator+ only)")
async def dismiss_alert(
    alert_id: str,
    body: DismissRequest,
    user: CurrentUser = Depends(require_operator),
):
    """
    FR-03.2: Alerts dismissible only by authorized roles.
    Dismissed alerts remain in audit log permanently.
    """
    alert = await alerts_col().find_one({"alertId": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.get("dismissedAt"):
        raise HTTPException(status_code=409, detail="Alert already dismissed")

    now = datetime.utcnow()
    await alerts_col().update_one(
        {"alertId": alert_id},
        {"$set": {"dismissedAt": now, "dismissedBy": user.user_id}},
    )

    # Audit log (immutable)
    await audit_logs_col().insert_one({
        "userId": user.user_id,
        "action": "DISMISS_ALERT",
        "timestamp": now,
        "metadata": {"alertId": alert_id, "reason": body.reason},
    })

    return APIResponse(message="Alert dismissed successfully")
