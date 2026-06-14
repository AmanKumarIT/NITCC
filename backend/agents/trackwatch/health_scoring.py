"""
TrackWatch Agent — Track Health Scoring Engine
PRD FR-07.1: Composite health score (0–100)
Components: Structural Integrity (40%) + Environmental Stress (25%) + Operational Load (20%) + Maintenance Recency (15%)
Scored every 6 hours; trend stored 2 years.
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.mongodb import track_segments_col, alerts_col, get_db
from shared.redis_client import check_and_register_alert, publish_dashboard_event
from shared.kafka_client import NitccKafkaProducer, KafkaTopic
from shared.schemas.models import (
    AlertSeverity, AlertDomain, TrackHealthComponents
)

logger = logging.getLogger(__name__)


# Default scoring thresholds (configurable via /config/reload)
DEFAULT_THRESHOLDS = {
    "failure_prob_work_order": 0.60,    # Auto-generate work order if failure prob > 60%
    "health_critical": 30,              # Below 30 → CRITICAL
    "health_warn": 60,                  # Below 60 → MEDIUM
    "bridge_age_watch": 50,             # Years; flag bridges older than this
    "inspection_overdue_days": 30,      # Days since last inspection before WATCH
}


class TrackHealthScorer:
    """
    Computes composite track health scores and manages alert generation.
    PRD FR-07.1 — Score formula:
      health_score = (structural_integrity * 0.40) +
                     (environmental_stress * 0.25) +
                     (operational_load * 0.20) +
                     (maintenance_recency * 0.15)
    """

    def __init__(self):
        self.thresholds = DEFAULT_THRESHOLDS.copy()

    def update_thresholds(self, new_thresholds: dict) -> None:
        self.thresholds.update(new_thresholds)
        logger.info(f"TrackHealthScorer thresholds updated: {new_thresholds}")

    def compute_health_score(
        self,
        structural_integrity: float,
        environmental_stress: float,
        operational_load: float,
        maintenance_recency: float,
    ) -> float:
        """
        Composite health score (0–100).
        All inputs are 0–100 sub-scores (higher = healthier).
        """
        score = (
            structural_integrity * 0.40
            + environmental_stress * 0.25
            + operational_load * 0.20
            + maintenance_recency * 0.15
        )
        return round(max(0.0, min(100.0, score)), 2)

    def compute_maintenance_recency_score(
        self, last_maintenance_date: Optional[datetime]
    ) -> float:
        """Higher score if maintained recently (< 7 days → 100, > 90 days → 0)."""
        if not last_maintenance_date:
            return 10.0  # Unknown maintenance = low score
        days_since = (datetime.utcnow() - last_maintenance_date).days
        if days_since <= 7:
            return 100.0
        elif days_since <= 30:
            return 80.0
        elif days_since <= 60:
            return 50.0
        elif days_since <= 90:
            return 25.0
        else:
            return max(0.0, 25.0 - (days_since - 90) * 0.5)

    async def process_sensor_reading(self, segment_id: str, payload: dict) -> None:
        """Update segment health based on incoming sensor data."""
        segment = await track_segments_col().find_one({"segmentId": segment_id})
        if not segment:
            logger.warning(f"Segment {segment_id} not found for sensor reading")
            return

        # Extract sensor data from payload
        vibration_index = payload.get("vibration_index", 100)   # 0–100 (100=no vibration)
        thermal_stress = payload.get("thermal_stress", 0)        # 0–100 (0=no stress)
        wheel_impact = payload.get("wheel_impact", 0)            # G-force accumulator

        # Update structural integrity based on sensor readings
        struct_score = max(0, 100 - vibration_index * 0.3 - thermal_stress * 0.2 - wheel_impact * 0.1)

        # Recompute full health score
        comps = segment.get("healthComponents", {})
        maintenance_score = self.compute_maintenance_recency_score(
            segment.get("lastMaintenanceDate")
        )

        new_health = self.compute_health_score(
            structural_integrity=struct_score,
            environmental_stress=comps.get("environmental_stress", 100),
            operational_load=comps.get("operational_load", 100),
            maintenance_recency=maintenance_score,
        )

        await track_segments_col().update_one(
            {"segmentId": segment_id},
            {
                "$set": {
                    "healthScore": new_health,
                    "healthComponents.structural_integrity": struct_score,
                    "healthComponents.maintenance_recency": maintenance_score,
                    "updatedAt": datetime.utcnow(),
                }
            }
        )

        await self._check_and_alert(segment_id, new_health, segment.get("fromStation"), segment.get("toStation"))

    async def score_all_segments(
        self,
        predictor,
        producer: NitccKafkaProducer,
        work_order_gen,
    ) -> None:
        """
        Full health scoring cycle for all track segments.
        Run every 6 hours (FR-07.1).
        Stores trend data in track_health_history collection.
        """
        cursor = track_segments_col().find({})
        async for segment in cursor:
            segment_id = segment.get("segmentId", "unknown")
            try:
                # Compute maintenance recency
                last_maint = segment.get("lastMaintenanceDate")
                maintenance_score = self.compute_maintenance_recency_score(last_maint)

                # Use existing stored sub-scores + maintenance recency
                comps = segment.get("healthComponents", {})
                new_health = self.compute_health_score(
                    structural_integrity=comps.get("structural_integrity", 100),
                    environmental_stress=comps.get("environmental_stress", 100),
                    operational_load=comps.get("operational_load", 100),
                    maintenance_recency=maintenance_score,
                )

                # ML failure probability prediction
                failure_prob = await predictor.predict_failure_probability(segment)

                # Update segment
                now = datetime.utcnow()
                await track_segments_col().update_one(
                    {"segmentId": segment_id},
                    {
                        "$set": {
                            "healthScore": new_health,
                            "failureProbability": failure_prob,
                            "healthComponents.maintenance_recency": maintenance_score,
                            "updatedAt": now,
                        }
                    }
                )

                # Store health history (2-year retention)
                await get_db()["track_health_history"].insert_one({
                    "segmentId": segment_id,
                    "healthScore": new_health,
                    "failureProbability": failure_prob,
                    "components": {
                        **comps,
                        "maintenance_recency": maintenance_score,
                    },
                    "recordedAt": now,
                })

                # FR-07.2: Flag bridges/tunnels with age > 50y or inspection overdue > 30d
                age_years = segment.get("ageYears", 0)
                is_bridge_or_tunnel = segment.get("isBridgeOrTunnel", False)
                days_since_maint = (now - last_maint).days if last_maint else 999

                if is_bridge_or_tunnel:
                    if age_years > self.thresholds["bridge_age_watch"]:
                        await self._create_alert(
                            segment_id, AlertSeverity.WARN,
                            f"Bridge/Tunnel {segment_id} age {age_years:.0f} years exceeds 50-year watch threshold"
                        )
                    if days_since_maint > self.thresholds["inspection_overdue_days"]:
                        await self._create_alert(
                            segment_id, AlertSeverity.WARN,
                            f"Bridge/Tunnel {segment_id}: inspection overdue by {days_since_maint - 30} days"
                        )

                # FR-02.1: Auto-generate work order if failure probability > threshold
                if failure_prob >= self.thresholds["failure_prob_work_order"]:
                    await work_order_gen.create_work_order(
                        segment_id, new_health, failure_prob
                    )

                # Check and alert based on health score
                await self._check_and_alert(
                    segment_id, new_health,
                    segment.get("fromStation"), segment.get("toStation")
                )

                # Publish health score event to Kafka
                await producer.publish(
                    topic=KafkaTopic.RAILWAY,
                    event_type="TRACK_HEALTH_SCORED",
                    payload={
                        "segmentId": segment_id,
                        "healthScore": new_health,
                        "failureProbability": failure_prob,
                    },
                    domain="operational",
                )

            except Exception as e:
                logger.error(f"Error scoring segment {segment_id}: {e}")

    async def _check_and_alert(
        self, segment_id: str, health_score: float,
        from_station: str = "", to_station: str = ""
    ) -> None:
        """Generate alerts based on health score thresholds."""
        if health_score < self.thresholds["health_critical"]:
            severity = AlertSeverity.CRITICAL
            msg = f"CRITICAL track health ({health_score:.1f}/100): {from_station}→{to_station}"
        elif health_score < self.thresholds["health_warn"]:
            severity = AlertSeverity.WARN
            msg = f"Track health degraded ({health_score:.1f}/100): {from_station}→{to_station}"
        else:
            return  # Healthy — no alert needed

        await self._create_alert(segment_id, severity, msg)

    async def _create_alert(
        self, segment_id: str, severity: AlertSeverity, message: str
    ) -> None:
        """Create alert with deduplication (FR-03.2 — 5-min suppression window)."""
        is_new = await check_and_register_alert(
            domain=AlertDomain.OPERATIONAL.value,
            severity=severity.value,
            message=message,
        )
        if not is_new:
            return  # Suppressed — duplicate within 5-minute window

        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        alert_doc = {
            "alertId": alert_id,
            "domain": AlertDomain.OPERATIONAL.value,
            "severity": severity.value,
            "sourceAgent": "trackwatch-agent",
            "segmentId": segment_id,
            "message": message,
            "metadata": {"segmentId": segment_id},
            "createdAt": datetime.utcnow(),
            "dismissedAt": None,
            "dismissedBy": None,
        }
        await alerts_col().insert_one(alert_doc)

        # Publish to Redis for WebSocket broadcast
        await publish_dashboard_event("nitcc.alerts", alert_doc)
        logger.info(f"Alert created: {alert_id} [{severity.value}] {message}")
