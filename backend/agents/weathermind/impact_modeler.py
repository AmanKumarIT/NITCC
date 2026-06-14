"""
WeatherMind Agent — Impact Modeler
PRD FR-05.2: Operational impact assessment per corridor + advisory generation
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.mongodb import weather_readings_col, alerts_col
from shared.redis_client import check_and_register_alert, publish_dashboard_event
from shared.kafka_client import NitccKafkaProducer, KafkaTopic
from shared.schemas.models import AlertSeverity, AlertDomain, WeatherImpactCode

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "flood_risk_critical":  0.75,
    "wind_speed_critical":  100,   # km/h
    "wind_speed_warn":      60,
    "visibility_critical":  0.5,   # km
    "visibility_warn":      1.0,
    "precipitation_critical": 50,  # mm/hr
    "precipitation_warn":   20,
    "temp_extreme_heat":    45,    # Celsius
}


class WeatherImpactModeler:
    """
    FR-05.2: Translates raw weather data into operational impact assessments.
    Generates speed restrictions and service advisories per corridor.
    """

    def __init__(self):
        self.thresholds = DEFAULT_THRESHOLDS.copy()

    def update_thresholds(self, new_thresholds: dict) -> None:
        self.thresholds.update(new_thresholds)

    async def assess_impact_and_generate_advisories(
        self, producer: NitccKafkaProducer
    ) -> List[Dict[str, Any]]:
        """
        Scan all latest weather readings and generate corridor advisories.
        Returns list of advisories created.
        """
        advisories = []

        # Get latest reading per corridor
        pipeline = [
            {"$sort": {"forecastedAt": -1}},
            {"$group": {"_id": "$corridorId", "latest": {"$first": "$$ROOT"}}},
        ]
        cursor = weather_readings_col().aggregate(pipeline)

        async for doc in cursor:
            reading = doc["latest"]
            corridor_id = reading.get("corridorId")
            advisory = await self._assess_corridor(corridor_id, reading, producer)
            if advisory:
                advisories.append(advisory)

        return advisories

    async def _assess_corridor(
        self, corridor_id: str, reading: dict, producer: NitccKafkaProducer
    ) -> dict | None:
        """Assess a single corridor weather reading and create advisory if needed."""
        thresholds = self.thresholds
        impacts = []
        severity = None

        wind_speed = reading.get("windSpeed", 0)
        precipitation = reading.get("precipitation", 0)
        visibility = reading.get("visibility", 15)
        flood_risk = reading.get("floodRisk", 0)
        temp = reading.get("temperature", 25)
        impact_code = reading.get("impactCode")

        # Check each condition
        if wind_speed > thresholds["wind_speed_critical"]:
            impacts.append(f"Extreme winds: {wind_speed:.0f} km/h — halt all trains")
            severity = AlertSeverity.CRITICAL
        elif wind_speed > thresholds["wind_speed_warn"]:
            impacts.append(f"High winds: {wind_speed:.0f} km/h — reduce speed to 60 km/h")
            severity = severity or AlertSeverity.WARN

        if precipitation > thresholds["precipitation_critical"]:
            impacts.append(f"Extreme rainfall: {precipitation:.0f} mm/hr — flood risk, halt trains")
            severity = AlertSeverity.CRITICAL
        elif precipitation > thresholds["precipitation_warn"]:
            impacts.append(f"Heavy rain: {precipitation:.0f} mm/hr — reduce speed, increase braking distance")
            severity = severity or AlertSeverity.WARN

        if visibility < thresholds["visibility_critical"]:
            impacts.append(f"Dense fog: visibility {visibility:.1f}km — halt trains, fog safety protocol")
            severity = AlertSeverity.CRITICAL
        elif visibility < thresholds["visibility_warn"]:
            impacts.append(f"Reduced visibility: {visibility:.1f}km — speed restriction 40 km/h")
            severity = severity or AlertSeverity.WARN

        if flood_risk > thresholds["flood_risk_critical"]:
            impacts.append(f"FLOOD RISK: {flood_risk:.0%} probability — section under watch")
            severity = AlertSeverity.CRITICAL

        if temp > thresholds["temp_extreme_heat"]:
            impacts.append(f"Extreme heat: {temp:.0f}°C — track expansion risk, speed restriction")
            severity = severity or AlertSeverity.WARN

        if not impacts or not severity:
            return None

        message = f"Corridor {corridor_id}: " + "; ".join(impacts)

        # Deduplication
        is_new = await check_and_register_alert("environmental", severity.value, message)
        if not is_new:
            return None

        advisory = {
            "alertId": f"ALT-{uuid.uuid4().hex[:8].upper()}",
            "domain": AlertDomain.ENVIRONMENTAL.value,
            "severity": severity.value,
            "sourceAgent": "weathermind-agent",
            "corridorId": corridor_id,
            "message": message,
            "impacts": impacts,
            "impactCode": impact_code,
            "metadata": {
                "windSpeed": wind_speed,
                "precipitation": precipitation,
                "visibility": visibility,
                "floodRisk": flood_risk,
                "temperature": temp,
            },
            "createdAt": datetime.utcnow(),
            "dismissedAt": None,
            "dismissedBy": None,
        }

        await alerts_col().insert_one(advisory)
        await publish_dashboard_event("nitcc.weather", advisory)

        # Publish to Kafka
        if producer:
            await producer.publish(
                topic=KafkaTopic.WEATHER,
                event_type="WEATHER_ADVISORY",
                payload={"corridorId": corridor_id, "severity": severity.value, "impacts": impacts},
                domain="environmental",
            )

        logger.warning(f"Weather advisory [{severity.value}] for corridor {corridor_id}")
        return advisory
