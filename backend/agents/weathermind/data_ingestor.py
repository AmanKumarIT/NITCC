"""
WeatherMind Agent — Data Ingestor
PRD FR-05.1: OpenWeather API (15-min) + IMD severe weather scraper
"""

from __future__ import annotations
import uuid
import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Optional

import httpx

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import settings
from shared.mongodb import weather_readings_col, get_db
from shared.schemas.models import WeatherReadingModel, WeatherImpactCode, GeoPoint

logger = logging.getLogger(__name__)


# Active corridor waypoints (seeded from NTES/config; in production loaded from DB)
SAMPLE_CORRIDOR_WAYPOINTS = [
    {"corridorId": "DELHI-MUMBAI", "name": "Delhi HQ", "lat": 28.6139, "lon": 77.2090},
    {"corridorId": "DELHI-MUMBAI", "name": "Kota", "lat": 25.1802, "lon": 75.8642},
    {"corridorId": "DELHI-MUMBAI", "name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    {"corridorId": "DELHI-KOLKATA", "name": "Patna", "lat": 25.5941, "lon": 85.1376},
    {"corridorId": "DELHI-KOLKATA", "name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    {"corridorId": "DELHI-CHENNAI", "name": "Nagpur", "lat": 21.1458, "lon": 79.0882},
    {"corridorId": "DELHI-CHENNAI", "name": "Chennai", "lat": 13.0827, "lon": 80.2707},
]


class WeatherDataIngestor:
    """
    Polls OpenWeather API every 15 minutes for all active corridor waypoints.
    Parses IMD severe weather warnings hourly.
    Writes to weather_readings MongoDB collection.
    """

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    async def fetch_openweather(self, lat: float, lon: float, corridor_id: str) -> Optional[dict]:
        """
        Fetch current weather + 7-day forecast from OpenWeather One Call API.
        FR-05.1: polls every 15 minutes for active corridors.
        """
        if not settings.openweather_api_key:
            logger.warning("OpenWeather API key not set — using mock data")
            return self._mock_weather(lat, lon, corridor_id)

        url = f"{settings.openweather_base_url}/onecall"
        params = {
            "lat": lat,
            "lon": lon,
            "exclude": "minutely,hourly",
            "appid": settings.openweather_api_key,
            "units": "metric",
        }
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return self._normalize_openweather(data, corridor_id, lat, lon)
        except httpx.HTTPError as e:
            logger.error(f"OpenWeather API error ({lat},{lon}): {e}")
            return None

    def _normalize_openweather(self, data: dict, corridor_id: str, lat: float, lon: float) -> dict:
        """Convert OpenWeather response to NITCC WeatherReading format."""
        current = data.get("current", {})
        weather_list = current.get("weather", [{}])
        main_weather = weather_list[0].get("main", "").lower() if weather_list else ""

        precipitation = 0.0
        rain = current.get("rain", {})
        snow = current.get("snow", {})
        if isinstance(rain, dict):
            precipitation += rain.get("1h", 0)
        if isinstance(snow, dict):
            precipitation += snow.get("1h", 0)

        impact_code = self._determine_impact_code(
            temp=current.get("temp", 20),
            wind_speed=current.get("wind_speed", 0) * 3.6,  # m/s → km/h
            visibility=current.get("visibility", 10000) / 1000,  # m → km
            precipitation=precipitation,
            main_weather=main_weather,
        )

        return {
            "readingId": f"WR-{uuid.uuid4().hex[:8].upper()}",
            "corridorId": corridor_id,
            "waypoint": {"type": "Point", "coordinates": [lon, lat]},
            "temperature": current.get("temp", 0),
            "precipitation": precipitation,
            "windSpeed": current.get("wind_speed", 0) * 3.6,
            "visibility": current.get("visibility", 10000) / 1000,
            "floodRisk": 0.0,  # Will be updated by WeatherMind impact modeler
            "impactCode": impact_code.value if impact_code else None,
            "forecastedAt": datetime.utcfromtimestamp(current.get("dt", datetime.utcnow().timestamp())),
            "source": "openweather",
            "raw": {k: v for k, v in current.items() if k not in ["weather"]},
        }

    def _determine_impact_code(
        self, temp: float, wind_speed: float, visibility: float,
        precipitation: float, main_weather: str
    ) -> Optional[WeatherImpactCode]:
        """Map weather conditions to NITCC impact codes (FR-05.2)."""
        if "thunderstorm" in main_weather and precipitation > 50:
            return WeatherImpactCode.FLOOD_RISK
        elif "cyclone" in main_weather or wind_speed > 120:
            return WeatherImpactCode.CYCLONE
        elif wind_speed > 60:
            return WeatherImpactCode.HIGH_WIND
        elif "fog" in main_weather or visibility < 0.5:
            return WeatherImpactCode.FOG
        elif temp > 45:
            return WeatherImpactCode.EXTREME_HEAT
        elif precipitation > 30:
            return WeatherImpactCode.FLOOD_RISK
        return None

    def _mock_weather(self, lat: float, lon: float, corridor_id: str) -> dict:
        """Generate simulated weather data for development."""
        import random
        reading_id = f"WR-{uuid.uuid4().hex[:8].upper()}"
        return {
            "readingId": reading_id,
            "corridorId": corridor_id,
            "waypoint": {"type": "Point", "coordinates": [lon, lat]},
            "temperature": round(random.uniform(20, 40), 1),
            "precipitation": round(random.uniform(0, 20), 1),
            "windSpeed": round(random.uniform(0, 50), 1),
            "visibility": round(random.uniform(2, 15), 1),
            "floodRisk": round(random.uniform(0, 0.3), 2),
            "impactCode": None,
            "forecastedAt": datetime.utcnow(),
            "source": "mock",
        }

    async def ingest_all_waypoints(self) -> None:
        """Fetch weather for all corridor waypoints and store in MongoDB."""
        tasks = [
            self.fetch_openweather(wp["lat"], wp["lon"], wp["corridorId"])
            for wp in SAMPLE_CORRIDOR_WAYPOINTS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        stored = 0
        for result in results:
            if isinstance(result, dict) and result:
                try:
                    await weather_readings_col().insert_one(result)
                    stored += 1
                except Exception as e:
                    logger.error(f"Error storing weather reading: {e}")
            elif isinstance(result, Exception):
                logger.error(f"Weather fetch error: {result}")

        logger.info(f"Weather ingestion complete: {stored}/{len(SAMPLE_CORRIDOR_WAYPOINTS)} waypoints updated")

    async def fetch_imd_warnings(self) -> List[dict]:
        """
        FR-05.1: Ingest IMD severe weather warnings via RSS/XML scraper.
        Falls back to empty list if IMD is unavailable.
        """
        if not settings.imd_api_url:
            return []
        try:
            response = await self._client.get(f"{settings.imd_api_url}/warnings.rss", timeout=15.0)
            root = ET.fromstring(response.text)
            warnings = []
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                desc = item.findtext("description", "")
                warnings.append({"title": title, "description": desc, "source": "imd"})
            return warnings
        except Exception as e:
            logger.warning(f"IMD feed unavailable: {e}")
            return []
