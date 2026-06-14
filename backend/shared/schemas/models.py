"""
NITCC Shared Pydantic Models & Enums
Mirrors MongoDB collection schemas from PRD Section 12.1
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId


# ─────────────────────────────────────────────────────────────────────────────
# Enums (PRD Section 12.1 + Appendix B)
# ─────────────────────────────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class AlertDomain(str, Enum):
    OPERATIONAL = "operational"
    ENVIRONMENTAL = "environmental"
    LOGISTICS = "logistics"
    EMERGENCY = "emergency"


class IncidentSeverity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    ACTIVE = "active"
    RESOLVED = "resolved"


class AgentStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SatelliteRiskType(str, Enum):
    LANDSLIDE = "landslide"
    FLOOD = "flood"
    ENCROACHMENT = "encroachment"
    EROSION = "erosion"


class WeatherImpactCode(str, Enum):
    FLOOD_RISK = "FLOOD_RISK"
    HIGH_WIND = "HIGH_WIND"
    FOG = "FOG"
    EXTREME_HEAT = "EXTREME_HEAT"
    CYCLONE = "CYCLONE"


class TrainStatus(str, Enum):
    MOVING = "moving"
    HALTED = "halted"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class CargoWagonStatus(str, Enum):
    IN_TRANSIT = "in_transit"
    AT_TERMINAL = "at_terminal"
    DELAYED = "delayed"
    HELD = "held"
    REROUTED = "rerouted"
    DELIVERED = "delivered"


class UserRole(str, Enum):
    READ_ONLY = "ReadOnly"
    OPERATOR = "Operator"
    SUPERVISOR = "Supervisor"
    EMERGENCY = "Emergency"
    ADMIN = "Admin"


class TrackHealthStatus(str, Enum):
    HEALTHY = "healthy"       # 80-100
    WATCH = "watch"           # 60-79
    DEGRADED = "degraded"     # 30-59
    CRITICAL = "critical"     # 0-29


# ─────────────────────────────────────────────────────────────────────────────
# GeoJSON Models
# ─────────────────────────────────────────────────────────────────────────────

class GeoPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]


class GeoLineString(BaseModel):
    type: str = "LineString"
    coordinates: List[List[float]]  # [[lng, lat], ...]


class GeoPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]  # [[[lng, lat], ...]]


# ─────────────────────────────────────────────────────────────────────────────
# MongoDB Collection Models (PRD Section 12.1)
# ─────────────────────────────────────────────────────────────────────────────

class TrainModel(BaseModel):
    """trains collection"""
    trainId: str
    corridorId: str
    currentPosition: GeoPoint
    speedKmh: float = 0.0
    riskScore: float = 0.0
    riskComponents: Dict[str, float] = Field(default_factory=dict)
    status: TrainStatus = TrainStatus.MOVING
    lastUpdated: datetime = Field(default_factory=datetime.utcnow)


class TrackHealthComponents(BaseModel):
    structural_integrity: float = 100.0  # 40% weight
    environmental_stress: float = 100.0  # 25% weight
    operational_load: float = 100.0      # 20% weight
    maintenance_recency: float = 100.0   # 15% weight


class TrackSegmentModel(BaseModel):
    """track_segments collection"""
    segmentId: str
    fromStation: str
    toStation: str
    geometry: GeoLineString
    healthScore: float = 100.0
    healthComponents: TrackHealthComponents = Field(default_factory=TrackHealthComponents)
    lastMaintenanceDate: Optional[datetime] = None
    ageYears: float = 0.0
    failureProbability: float = 0.0
    alerts: List[str] = Field(default_factory=list)   # alert IDs
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    @property
    def health_status(self) -> TrackHealthStatus:
        if self.healthScore >= 80:
            return TrackHealthStatus.HEALTHY
        elif self.healthScore >= 60:
            return TrackHealthStatus.WATCH
        elif self.healthScore >= 30:
            return TrackHealthStatus.DEGRADED
        return TrackHealthStatus.CRITICAL


class AlertModel(BaseModel):
    """alerts collection"""
    alertId: str
    domain: AlertDomain
    severity: AlertSeverity
    sourceAgent: str
    trainId: Optional[str] = None
    segmentId: Optional[str] = None
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    dismissedAt: Optional[datetime] = None
    dismissedBy: Optional[str] = None

    @property
    def is_dismissed(self) -> bool:
        return self.dismissedAt is not None


class ActionPlanVersion(BaseModel):
    version: int
    editedBy: str
    editedAt: datetime
    rationale: str
    snapshot: Dict[str, Any]


class ActionPlan(BaseModel):
    immediate_actions: List[str]
    agency_contacts: List[Dict[str, str]]
    resource_list: List[Dict[str, Any]]
    evacuation_routes: List[str]
    communication_template: str
    generatedAt: datetime = Field(default_factory=datetime.utcnow)
    versions: List[ActionPlanVersion] = Field(default_factory=list)


class IncidentTimeline(BaseModel):
    timestamp: datetime
    event: str
    actor: str  # userId or agentId
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentModel(BaseModel):
    """incidents collection"""
    incidentId: str
    type: str
    severity: IncidentSeverity
    location: GeoPoint
    status: IncidentStatus = IncidentStatus.DETECTED
    affectedTrains: List[str] = Field(default_factory=list)
    affectedSegments: List[str] = Field(default_factory=list)
    actionPlan: Optional[ActionPlan] = None
    timeline: List[IncidentTimeline] = Field(default_factory=list)
    dataSources: List[str] = Field(default_factory=list)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    resolvedAt: Optional[datetime] = None


class WeatherReadingModel(BaseModel):
    """weather_readings collection"""
    readingId: str
    corridorId: str
    waypoint: GeoPoint
    temperature: float  # Celsius
    precipitation: float  # mm/hr
    windSpeed: float  # km/h
    visibility: float  # km
    floodRisk: float = 0.0  # 0–1 probability
    impactCode: Optional[WeatherImpactCode] = None
    forecastedAt: datetime
    source: str  # openweather | imd


class SatelliteRiskZoneModel(BaseModel):
    """satellite_risk_zones collection"""
    zoneId: str
    geometry: GeoPolygon
    riskType: SatelliteRiskType
    riskTier: RiskTier
    analysisDate: datetime
    dataSource: str  # bhuvan | nasa_modis | landsat
    changeDetected: bool = False
    previousZoneId: Optional[str] = None


class CargoException(BaseModel):
    type: str
    description: str
    timestamp: datetime
    resolved: bool = False


class CargoWagonModel(BaseModel):
    """cargo_wagons collection"""
    wagonId: str
    trainId: Optional[str] = None
    currentPosition: GeoPoint
    cargo: Dict[str, Any] = Field(default_factory=dict)
    origin: str
    destination: str
    eta: Optional[datetime] = None
    status: CargoWagonStatus = CargoWagonStatus.IN_TRANSIT
    exceptions: List[CargoException] = Field(default_factory=list)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)


class AuditEvent(BaseModel):
    action: str
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UserModel(BaseModel):
    """users collection"""
    userId: str
    email: str
    passwordHash: str
    roles: List[UserRole] = Field(default_factory=list)
    jurisdictionZones: List[str] = Field(default_factory=list)
    mfaEnabled: bool = True
    mfaSecret: Optional[str] = None
    lastLogin: Optional[datetime] = None
    auditEvents: List[AuditEvent] = Field(default_factory=list)
    isActive: bool = True


class AgentMetricsSnapshot(BaseModel):
    events_processed_total: int = 0
    inference_duration_seconds_avg: float = 0.0
    error_rate: float = 0.0
    kafka_lag: int = 0


class AgentStateModel(BaseModel):
    """agent_state collection"""
    agentId: str
    agentName: str
    status: AgentStatus = AgentStatus.RUNNING
    lastHeartbeat: datetime = Field(default_factory=datetime.utcnow)
    currentContext: Dict[str, Any] = Field(default_factory=dict)
    metricsSnapshot: AgentMetricsSnapshot = Field(default_factory=AgentMetricsSnapshot)


# ─────────────────────────────────────────────────────────────────────────────
# API Request/Response models
# ─────────────────────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    """Standard API response envelope (PRD Section 11.1)"""
    status: str = "success"
    code: int = 200
    message: str = "OK"
    data: Any = None


class PaginatedResponse(BaseModel):
    status: str = "success"
    code: int = 200
    message: str = "OK"
    data: List[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


class WorkOrder(BaseModel):
    workOrderId: str
    segmentId: str
    healthScore: float
    failureProbability: float
    priority: str  # CRITICAL | HIGH | MEDIUM | LOW
    recommendedAction: str
    estimatedDuration: str
    assignedZone: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending | in_progress | completed


# ─────────────────────────────────────────────────────────────────────────────
# Kafka Event Envelope
# ─────────────────────────────────────────────────────────────────────────────

class KafkaEvent(BaseModel):
    """Standard Kafka message envelope — Avro schema v2 (Appendix A)"""
    agentId: str
    eventType: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlationId: str
    domain: AlertDomain
    payload: Dict[str, Any]
    schemaVersion: str = "2.0"
