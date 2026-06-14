"""
NITCC Database Seed Script
Populates MongoDB with initial data for development and demonstration.
Run: python scripts/seed_database.py
"""

import asyncio
import uuid
import random
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB_NAME", "nitcc_dev")

CORRIDORS = [
    {"id": "DELHI-MUMBAI", "name": "Delhi–Mumbai Corridor", "color": "#1E6FD9"},
    {"id": "DELHI-KOLKATA", "name": "Delhi–Kolkata Corridor", "color": "#10B981"},
    {"id": "DELHI-CHENNAI", "name": "Delhi–Chennai Corridor", "color": "#F59E0B"},
    {"id": "MUMBAI-CHENNAI", "name": "Mumbai–Chennai Corridor", "color": "#8B5CF6"},
    {"id": "KOLKATA-CHENNAI", "name": "Kolkata–Chennai Corridor", "color": "#EF4444"},
]

STATIONS = {
    "DELHI-MUMBAI": [
        ("New Delhi", 28.6139, 77.2090),
        ("Mathura", 27.4924, 77.6737),
        ("Agra", 27.1767, 78.0081),
        ("Kota", 25.1802, 75.8642),
        ("Vadodara", 22.3072, 73.1812),
        ("Surat", 21.1702, 72.8311),
        ("Mumbai", 19.0760, 72.8777),
    ],
    "DELHI-KOLKATA": [
        ("New Delhi", 28.6139, 77.2090),
        ("Kanpur", 26.4499, 80.3319),
        ("Allahabad", 25.4358, 81.8463),
        ("Varanasi", 25.3176, 82.9739),
        ("Patna", 25.5941, 85.1376),
        ("Dhanbad", 23.7957, 86.4304),
        ("Kolkata", 22.5726, 88.3639),
    ],
    "DELHI-CHENNAI": [
        ("New Delhi", 28.6139, 77.2090),
        ("Bhopal", 23.2599, 77.4126),
        ("Nagpur", 21.1458, 79.0882),
        ("Hyderabad", 17.3850, 78.4867),
        ("Vijayawada", 16.5062, 80.6480),
        ("Chennai", 13.0827, 80.2707),
    ],
}


async def seed_trains(db):
    """Seed 50 active trains across all corridors."""
    trains = []
    for corridor in CORRIDORS:
        num_trains = random.randint(5, 12)
        stations = STATIONS.get(corridor["id"], [])
        if not stations:
            stations = [("Delhi", 28.6, 77.2), ("Mumbai", 19.0, 72.8)]

        for i in range(num_trains):
            # Random position between two stations
            s1 = random.choice(stations)
            lat_jitter = random.uniform(-0.5, 0.5)
            lon_jitter = random.uniform(-0.5, 0.5)
            risk = random.uniform(5, 95)

            trains.append({
                "trainId": f"TRN-{corridor['id'][:3]}-{1000 + i}",
                "corridorId": corridor["id"],
                "currentPosition": {
                    "type": "Point",
                    "coordinates": [s1[2] + lon_jitter, s1[1] + lat_jitter]
                },
                "speedKmh": random.uniform(0, 130),
                "safeSpeedLimit": 110,
                "riskScore": round(risk, 2),
                "riskComponents": {
                    "track_risk": round(random.uniform(0, 50), 2),
                    "weather_severity": round(random.uniform(0, 30), 2),
                    "speed_factor": round(random.uniform(0, 40), 2),
                    "cargo_weight_factor": round(random.uniform(0, 30), 2),
                },
                "status": random.choice(["moving", "moving", "moving", "halted", "delayed"]),
                "cargoWeightTons": round(random.uniform(200, 3000), 1),
                "maxCapacityTons": 3000,
                "lastUpdated": datetime.utcnow().isoformat(),
            })

    if trains:
        await db.trains.delete_many({})
        await db.trains.insert_many(trains)
        print(f"✅ Seeded {len(trains)} trains")


async def seed_track_segments(db):
    """Seed track segments for all corridors."""
    segments = []
    for corridor_id, stations in STATIONS.items():
        for i in range(len(stations) - 1):
            s1 = stations[i]
            s2 = stations[i + 1]
            health = random.uniform(20, 98)
            age_years = random.uniform(5, 70)

            segments.append({
                "segmentId": f"SEG-{corridor_id}-{i+1:02d}",
                "corridorId": corridor_id,
                "fromStation": s1[0],
                "toStation": s2[0],
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [s1[2], s1[1]],
                        [(s1[2] + s2[2]) / 2, (s1[1] + s2[1]) / 2],
                        [s2[2], s2[1]],
                    ]
                },
                "healthScore": round(health, 2),
                "failureProbability": round(max(0, (100 - health) / 150), 4),
                "healthComponents": {
                    "structural_integrity": round(random.uniform(60, 100), 2),
                    "environmental_stress": round(random.uniform(50, 100), 2),
                    "operational_load": round(random.uniform(60, 100), 2),
                    "maintenance_recency": round(random.uniform(40, 100), 2),
                },
                "ageYears": round(age_years, 1),
                "isBridgeOrTunnel": random.random() < 0.15,
                "lastMaintenanceDate": (datetime.utcnow() - timedelta(days=random.randint(1, 90))).isoformat(),
                "updatedAt": datetime.utcnow().isoformat(),
            })

    if segments:
        await db.track_segments.delete_many({})
        await db.track_segments.insert_many(segments)
        print(f"✅ Seeded {len(segments)} track segments")


async def seed_alerts(db):
    """Seed sample alerts."""
    alerts = []
    for i in range(15):
        severity = random.choice(["CRITICAL", "CRITICAL", "WARN", "WARN", "WARN", "INFO"])
        domain = random.choice(["operational", "environmental", "logistics", "emergency"])
        corridor = random.choice(CORRIDORS)

        alerts.append({
            "alertId": f"ALT-{uuid.uuid4().hex[:8].upper()}",
            "domain": domain,
            "severity": severity,
            "sourceAgent": random.choice(["trackwatch-agent", "weathermind-agent", "sateye-agent"]),
            "corridorId": corridor["id"],
            "message": f"[{severity}] {domain.title()} alert for {corridor['name']}: Risk detected at segment {random.randint(1, 10)}",
            "metadata": {},
            "createdAt": (datetime.utcnow() - timedelta(minutes=random.randint(0, 120))).isoformat(),
            "dismissedAt": None,
            "dismissedBy": None,
        })

    if alerts:
        await db.alerts.delete_many({})
        await db.alerts.insert_many(alerts)
        print(f"✅ Seeded {len(alerts)} alerts")


async def seed_users(db):
    """Seed demo users for each role."""
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

    users = [
        {"email": "admin@nitcc.gov.in", "name": "Admin User", "roles": ["Admin"], "zones": []},
        {"email": "supervisor@nitcc.gov.in", "name": "Zone Supervisor", "roles": ["Supervisor"], "zones": ["DELHI-MUMBAI", "DELHI-KOLKATA"]},
        {"email": "operator@nitcc.gov.in", "name": "Control Room Operator", "roles": ["Operator"], "zones": ["DELHI-MUMBAI"]},
        {"email": "emergency@nitcc.gov.in", "name": "Emergency Coordinator", "roles": ["Emergency"], "zones": []},
        {"email": "readonly@nitcc.gov.in", "name": "Read-Only User", "roles": ["ReadOnly"], "zones": []},
    ]

    for user in users:
        user_doc = {
            "userId": f"USR-{uuid.uuid4().hex[:8].upper()}",
            "email": user["email"],
            "name": user["name"],
            "passwordHash": pwd.hash("nitcc@2026"),  # Default demo password
            "roles": user["roles"],
            "jurisdictionZones": user["zones"],
            "mfaEnabled": False,
            "mfaSecret": None,
            "isActive": True,
            "lastLogin": None,
            "createdAt": datetime.utcnow().isoformat(),
        }
        await db.users.update_one(
            {"email": user["email"]},
            {"$set": user_doc},
            upsert=True
        )

    print(f"✅ Seeded {len(users)} demo users")
    print("   Default password: nitcc@2026")
    for u in users:
        print(f"   {u['email']} ({u['roles'][0]})")


async def seed_incidents(db):
    """Seed sample incidents."""
    incidents = [
        {
            "incidentId": "INC-DEMO-001",
            "type": "Landslide Block",
            "severity": "P2",
            "location": {"type": "Point", "coordinates": [73.3, 19.5]},
            "status": "active",
            "affectedTrains": ["TRN-DEL-1001", "TRN-DEL-1002"],
            "affectedSegments": ["SEG-DELHI-MUMBAI-03"],
            "actionPlan": None,  # CrisisCommand will generate
            "dataSources": ["trackwatch-agent", "weathermind-agent"],
            "timeline": [
                {
                    "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                    "event": "Incident auto-detected: landslide risk zone activated",
                    "actor": "sateye-agent",
                    "metadata": {},
                }
            ],
            "createdAt": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "resolvedAt": None,
        },
    ]
    await db.incidents.delete_many({})
    await db.incidents.insert_many(incidents)
    print(f"✅ Seeded {len(incidents)} incidents")


async def main():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]

    print(f"\n🚀 NITCC Database Seed Script")
    print(f"   MongoDB: {MONGODB_URI}")
    print(f"   Database: {DB_NAME}\n")

    await seed_trains(db)
    await seed_track_segments(db)
    await seed_alerts(db)
    await seed_incidents(db)
    await seed_users(db)

    print(f"\n✅ Database seeding complete!")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
