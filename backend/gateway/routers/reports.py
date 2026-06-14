"""
Reports Router
POST /reports/generate
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
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