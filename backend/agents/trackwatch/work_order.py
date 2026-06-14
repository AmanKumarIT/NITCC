"""
TrackWatch Agent — Work Order Generator
PRD FR-07.3: Auto-generated maintenance work orders (JSON + PDF export)
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.mongodb import track_segments_col, work_orders_col

logger = logging.getLogger(__name__)


def _priority_from_scores(health_score: float, failure_prob: float) -> str:
    if health_score < 30 or failure_prob > 0.80:
        return "CRITICAL"
    elif health_score < 60 or failure_prob > 0.60:
        return "HIGH"
    elif health_score < 80 or failure_prob > 0.40:
        return "MEDIUM"
    return "LOW"


class WorkOrderGenerator:
    """
    Generates structured maintenance work orders for track segments.
    FR-07.3: Exportable as JSON/PDF; field team status updates ingestible via API.
    """

    async def create_work_order(
        self,
        segment_id: str,
        health_score: float,
        failure_prob: float,
        reason: Optional[str] = None,
    ) -> dict:
        """
        Create a maintenance work order for a track segment.
        Idempotent — skips if an open work order already exists for this segment.
        """
        # Check for existing open work order
        existing = await work_orders_col().find_one({
            "segmentId": segment_id,
            "status": {"$in": ["pending", "in_progress"]},
        })
        if existing:
            logger.debug(f"Open work order already exists for segment {segment_id}")
            return existing

        # Get segment info
        segment = await track_segments_col().find_one({"segmentId": segment_id}, {"_id": 0})
        if not segment:
            logger.warning(f"Segment {segment_id} not found when creating work order")
            return {}

        priority = _priority_from_scores(health_score, failure_prob)

        # Determine recommended action based on score severity
        if health_score < 30:
            action = "IMMEDIATE CLOSURE AND REPLACEMENT: Track section must be taken out of service for emergency repair"
        elif health_score < 50:
            action = "URGENT INSPECTION AND REPAIR: Deploy engineering gang within 24 hours for structural assessment"
        elif health_score < 70:
            action = "SCHEDULED MAINTENANCE: Plan maintenance window within 7 days; reduce train speed limit to 60 km/h"
        else:
            action = "ROUTINE INSPECTION: Schedule inspection within 30 days; monitor closely"

        wo_id = f"WO-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()

        work_order = {
            "workOrderId": wo_id,
            "segmentId": segment_id,
            "fromStation": segment.get("fromStation", ""),
            "toStation": segment.get("toStation", ""),
            "healthScore": round(health_score, 2),
            "failureProbability": round(failure_prob, 4),
            "priority": priority,
            "recommendedAction": action,
            "estimatedDuration": self._estimate_duration(priority),
            "assignedZone": segment.get("corridorId", ""),
            "reason": reason or f"Auto-generated: failure probability {failure_prob:.0%}",
            "status": "pending",
            "createdAt": now,
            "updatedAt": now,
            "completedAt": None,
            "fieldNotes": [],
        }

        await work_orders_col().insert_one(work_order)
        work_order.pop("_id", None)
        logger.info(f"Work order created: {wo_id} [{priority}] for segment {segment_id}")
        return work_order

    def _estimate_duration(self, priority: str) -> str:
        durations = {
            "CRITICAL": "1–3 days (emergency)",
            "HIGH": "3–7 days",
            "MEDIUM": "1–2 weeks",
            "LOW": "1 month",
        }
        return durations.get(priority, "TBD")

    @staticmethod
    def to_json(work_order: dict) -> dict:
        """Returns work order as structured JSON (FR-07.3)."""
        return {k: v for k, v in work_order.items() if k != "_id"}

    @staticmethod
    def to_pdf_bytes(work_order: dict) -> bytes:
        """
        Generate PDF of work order using reportlab.
        Returns PDF as bytes for download.
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
            from reportlab.lib import colors
            import io

            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # Header
            story.append(Paragraph("NITCC — Maintenance Work Order", styles["Title"]))
            story.append(Spacer(1, 12))

            # Work order details table
            data = [
                ["Work Order ID", work_order.get("workOrderId", "")],
                ["Segment", f"{work_order.get('fromStation')} → {work_order.get('toStation')}"],
                ["Priority", work_order.get("priority", "")],
                ["Health Score", f"{work_order.get('healthScore', 0):.1f}/100"],
                ["Failure Probability", f"{work_order.get('failureProbability', 0):.1%}"],
                ["Recommended Action", work_order.get("recommendedAction", "")],
                ["Estimated Duration", work_order.get("estimatedDuration", "")],
                ["Status", work_order.get("status", "pending")],
                ["Created At", str(work_order.get("createdAt", ""))],
            ]

            t = Table(data, colWidths=[150, 350])
            t.setStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("WORDWRAP", (1, 5), (1, 5), "WORD"),
            ])
            story.append(t)

            doc.build(story)
            return buf.getvalue()

        except ImportError:
            logger.warning("reportlab not installed; PDF export unavailable")
            return b""
