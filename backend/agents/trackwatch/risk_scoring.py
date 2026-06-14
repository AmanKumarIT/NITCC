"""
TrackWatch Agent — Accident Risk Index Scorer
PRD FR-02.2: Risk index (0–100) per active train, updated every 60 seconds.
Risk > 70 → WARN; > 90 → CRITICAL (auto-generate alerts)
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime
from typing import Dict, Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.mongodb import trains_col, alerts_col, track_segments_col, weather_readings_col
from shared.redis_client import check_and_register_alert, publish_dashboard_event
from shared.kafka_client import NitccKafkaProducer, KafkaTopic
from shared.schemas.models import AlertSeverity, AlertDomain, TrainStatus

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "risk_warn": 70,
    "risk_critical": 90,
}


class AccidentRiskScorer:
    """
    Computes Accident Risk Index (0–100) per train by combining:
    - Track health score (weight: 30%)
    - Weather severity (weight: 25%)
    - Train speed vs. safe speed (weight: 25%)
    - Cargo weight factor (weight: 20%)
    """

    def __init__(self):
        self.thresholds = DEFAULT_THRESHOLDS.copy()

    def update_thresholds(self, new_thresholds: dict) -> None:
        self.thresholds.update(new_thresholds)

    def compute_risk_index(
        self,
        track_health: float,
        weather_severity: float,
        speed_factor: float,
        cargo_weight_factor: float,
    ) -> tuple[float, Dict[str, float]]:
        """
        Returns (risk_index, components_dict).
        All inputs: 0–100 where 100 = maximum risk contribution.
        track_health input is 0–100 health score → inverted → risk contribution
        """
        track_risk = max(0, 100 - track_health)   # Low health = high risk

        risk = (
            track_risk        * 0.30
            + weather_severity  * 0.25
            + speed_factor      * 0.25
            + cargo_weight_factor * 0.20
        )

        risk_index = round(max(0.0, min(100.0, risk)), 2)
        components = {
            "track_risk": round(track_risk, 2),
            "weather_severity": round(weather_severity, 2),
            "speed_factor": round(speed_factor, 2),
            "cargo_weight_factor": round(cargo_weight_factor, 2),
        }
        return risk_index, components

    async def update_train_risk(self, train_id: str, telemetry: dict) -> None:
        """Process a single telemetry update for one train."""
        await self._score_train(train_id, telemetry)

    async def score_all_active_trains(self, producer: NitccKafkaProducer) -> None:
        """Score all trains currently in motion (status=MOVING or DELAYED)."""
        cursor = trains_col().find(
            {"status": {"$in": ["moving", "delayed"]}},
        )
        async for train in cursor:
            train_id = train.get("trainId")
            try:
                await self._score_train(train_id, train, producer)
            except Exception as e:
                logger.error(f"Error scoring train {train_id}: {e}")

    async def _score_train(
        self, train_id: str, data: dict, producer: NitccKafkaProducer = None
    ) -> None:
        """Compute and persist risk score for a single train."""
        # 1. Get current track segment health
        corridor_id = data.get("corridorId", "")
        segment = await track_segments_col().find_one({"segmentId": corridor_id})
        track_health = segment.get("healthScore", 100.0) if segment else 100.0

        # 2. Get weather severity for this corridor
        weather = await weather_readings_col().find_one(
            {"corridorId": corridor_id},
            sort=[("forecastedAt", -1)],
        )
        weather_severity = self._compute_weather_severity(weather) if weather else 0.0

        # 3. Speed factor: how fast vs. safe speed limit
        speed_kmh = data.get("speedKmh", 0)
        safe_speed = data.get("safeSpeedLimit", 100)
        speed_factor = min(100.0, (speed_kmh / max(safe_speed, 1)) * 100) if safe_speed else 0.0

        # 4. Cargo weight factor
        cargo_weight_tons = data.get("cargoWeightTons", 0)
        max_capacity_tons = data.get("maxCapacityTons", 1000)
        cargo_factor = min(100.0, (cargo_weight_tons / max(max_capacity_tons, 1)) * 100)

        # 5. Compute composite risk index
        risk_index, components = self.compute_risk_index(
            track_health=track_health,
            weather_severity=weather_severity,
            speed_factor=speed_factor,
            cargo_weight_factor=cargo_factor,
        )

        # 6. Persist to MongoDB
        now = datetime.utcnow()
        await trains_col().update_one(
            {"trainId": train_id},
            {
                "$set": {
                    "riskScore": risk_index,
                    "riskComponents": components,
                    "lastUpdated": now,
                }
            }
        )

        # 7. Alert if threshold crossed
        await self._check_risk_alerts(train_id, risk_index, corridor_id)

        # 8. Publish risk update event
        if producer:
            await producer.publish(
                topic=KafkaTopic.RAILWAY,
                event_type="TRAIN_RISK_UPDATED",
                payload={
                    "trainId": train_id,
                    "riskScore": risk_index,
                    "riskComponents": components,
                    "corridorId": corridor_id,
                },
                domain="operational",
            )

        # 9. Broadcast to WebSocket dashboard
        await publish_dashboard_event("nitcc.railway", {
            "type": "RISK_UPDATE",
            "trainId": train_id,
            "riskScore": risk_index,
            "timestamp": now.isoformat(),
        })

    def _compute_weather_severity(self, weather: dict) -> float:
        """Convert weather reading to 0–100 severity score."""
        if not weather:
            return 0.0

        score = 0.0
        # Precipitation: >50mm/hr = 100
        precip = weather.get("precipitation", 0)
        score += min(100, precip * 2) * 0.3

        # Wind speed: >100km/h = 100
        wind = weather.get("windSpeed", 0)
        score += min(100, wind) * 0.2

        # Visibility: <1km = 100
        vis = weather.get("visibility", 10)
        score += max(0, (10 - vis) / 10 * 100) * 0.2

        # Flood risk: 0–1 probability
        flood = weather.get("floodRisk", 0)
        score += flood * 100 * 0.3

        return round(min(100.0, score), 2)

    async def _check_risk_alerts(self, train_id: str, risk_index: float, corridor_id: str) -> None:
        if risk_index > self.thresholds["risk_critical"]:
            severity = AlertSeverity.CRITICAL
            msg = f"Train {train_id} CRITICAL risk index: {risk_index:.1f}/100 on corridor {corridor_id}"
        elif risk_index > self.thresholds["risk_warn"]:
            severity = AlertSeverity.WARN
            msg = f"Train {train_id} elevated risk index: {risk_index:.1f}/100 on corridor {corridor_id}"
        else:
            return

        is_new = await check_and_register_alert("operational", severity.value, msg)
        if not is_new:
            return

        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        await alerts_col().insert_one({
            "alertId": alert_id,
            "domain": AlertDomain.OPERATIONAL.value,
            "severity": severity.value,
            "sourceAgent": "trackwatch-agent",
            "trainId": train_id,
            "message": msg,
            "metadata": {"riskScore": risk_index, "corridorId": corridor_id},
            "createdAt": datetime.utcnow(),
            "dismissedAt": None,
            "dismissedBy": None,
        })
        await publish_dashboard_event("nitcc.alerts", {"alertId": alert_id, "severity": severity.value, "message": msg})
        logger.warning(f"Risk alert: [{severity.value}] {msg}")
