# NITCC — National Intelligent Transportation Command Center

> AI-powered multi-agent intelligence platform for India's national transportation network.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Dashboard (Vite + TypeScript)          │
│              12 Screens (S1–S12) · Mapbox GL JS · WebSocket     │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST + WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                    API Gateway (FastAPI)                          │
│          JWT Auth · RBAC · Rate Limiting · Prometheus            │
└───┬────────────────────────────────────────────┬────────────────┘
    │ MongoDB Atlas                               │ Redis (pub/sub)
    │                                            │
┌───▼────────────────────────────────────────────▼────────────────┐
│                     Kafka Event Bus                              │
│    nitcc.railway · nitcc.weather · nitcc.satellite               │
│    nitcc.logistics · nitcc.emergency · nitcc.alerts              │
└──┬─────┬──────┬──────┬──────┬──────┬──────────────────────────┘
   │     │      │      │      │      │
   ▼     ▼      ▼      ▼      ▼      ▼
Track WeatherMind SatEye CrisisCmd CargoFlow Orchestrator
Watch  Agent    Agent   Agent    Agent    (LangGraph)
FR-02  FR-05   FR-04  FR-06   FR-08    FR-01
FR-07
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker Desktop
- MongoDB Atlas account (or local MongoDB)

### 1. Environment Setup

```bash
# Clone and enter project
cd NITCC

# Copy environment templates
cp .env.example .env
cp frontend/.env.example frontend/.env

# Edit .env with your API keys:
#   MONGODB_URI, OPENWEATHER_API_KEY, MAPBOX_ACCESS_TOKEN
#   LLM_API_KEY, LLM_PROVIDER, LLM_MODEL
nano .env
```

### 2. Start Infrastructure (Docker)

```bash
docker-compose -f docker-compose.dev.yml up -d
```

This starts: Kafka, Redis, ELK Stack, Prometheus, Grafana, Airflow, MLflow.

### 3. Backend Setup

```bash
cd backend

# Install shared package
pip install -e shared/
pip install -r requirements.txt

# Seed database
python ../scripts/seed_database.py

# Start API Gateway
uvicorn gateway.main:app --reload --port 8000
```

### 4. Start Agents (separate terminals)

```bash
# TrackWatch Agent
uvicorn agents.trackwatch.main:app --port 8001 --reload

# WeatherMind Agent
uvicorn agents.weathermind.main:app --port 8002 --reload

# SatEye Agent
uvicorn agents.sateye.main:app --port 8003 --reload

# CrisisCommand Agent
uvicorn agents.crisiscommand.main:app --port 8004 --reload

# CargoFlow Agent
uvicorn agents.cargoflow.main:app --port 8005 --reload

# Orchestrator Agent
uvicorn agents.orchestrator.main:app --port 8007 --reload
```

### 5. Start Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

## Demo Users

| Email | Password | Role |
|-------|----------|------|
| admin@nitcc.gov.in | nitcc@2026 | Admin |
| supervisor@nitcc.gov.in | nitcc@2026 | Supervisor |
| operator@nitcc.gov.in | nitcc@2026 | Operator |
| emergency@nitcc.gov.in | nitcc@2026 | Emergency |
| readonly@nitcc.gov.in | nitcc@2026 | ReadOnly |

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `MONGODB_URI` | MongoDB Atlas connection string |
| `REDIS_URL` | Redis connection URL |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address |
| `LLM_PROVIDER` | `openai` / `google` / `anthropic` |
| `LLM_MODEL` | Model name (e.g. `gpt-4o`) |
| `LLM_API_KEY` | LLM API key |
| `MAPBOX_ACCESS_TOKEN` | Mapbox public access token |
| `OPENWEATHER_API_KEY` | OpenWeather API key |
| `APP_SECRET_KEY` | JWT signing secret (min 32 chars) |

## Project Structure

```
NITCC/
├── backend/
│   ├── shared/              # Shared: config, schemas, MongoDB, Redis, Kafka, Auth
│   ├── gateway/             # API Gateway (FastAPI, REST + WebSocket)
│   │   └── routers/         # trains, alerts, incidents, weather, satellite, cargo...
│   ├── agents/
│   │   ├── trackwatch/      # FR-02, FR-07: Track health + accident risk
│   │   ├── weathermind/     # FR-05: Weather ingestion + impact modeling
│   │   ├── sateye/          # FR-04: Satellite image analysis
│   │   ├── crisiscommand/   # FR-06: LLM action plan generation
│   │   ├── cargoflow/       # FR-08: Freight logistics + route optimization
│   │   └── orchestrator/    # FR-01: LangGraph state machine
│   ├── airflow/dags/        # Airflow DAGs: ingestion + ML retraining
│   ├── ml_models/           # TensorFlow SavedModel storage
│   └── requirements.txt
├── frontend/                # React + Vite + TypeScript
│   └── src/
│       ├── pages/           # S1–S12 screens
│       ├── components/      # Reusable UI components
│       ├── store/           # Zustand: auth + dashboard state
│       ├── services/        # Axios API client
│       ├── hooks/           # useWebSocket (auto-reconnect)
│       └── styles/          # NITCC design system CSS
├── scripts/
│   └── seed_database.py     # MongoDB seed data
├── docker-compose.dev.yml   # Infrastructure services
└── .env.example             # Environment template
```

## API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs: `http://localhost:8000/docs`

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login (Step 1) |
| POST | `/auth/mfa/verify` | MFA verification (Step 2) |
| GET | `/trains` | Active train list |
| GET | `/alerts` | Alert list (filterable) |
| POST | `/alerts/{id}/dismiss` | Dismiss alert (Operator+) |
| GET | `/incidents` | Incident list |
| POST | `/incidents` | Declare incident manually |
| GET | `/incidents/{id}/action-plan` | Fetch AI action plan |
| GET | `/tracks` | Track segment health |
| GET | `/weather/corridors` | Weather per corridor |
| GET | `/satellite/risk-zones` | Satellite risk zones (GeoJSON) |
| GET | `/cargo/wagons` | Freight wagon status |
| POST | `/cargo/routes/recommend` | Route optimization |
| GET | `/agents/status` | Agent health (Admin) |
| WS | `/ws/dashboard?token=JWT` | Real-time event feed |

## Key Features (PRD Compliance)

| PRD Requirement | Implementation |
|----------------|----------------|
| FR-01: Multi-Agent Orchestration | LangGraph state machine in Orchestrator |
| FR-02: Accident Risk Index | TrackWatch: composite score (0–100) per train, 60s update |
| FR-03: Alert System | 5-min deduplication, RBAC dismiss, WebSocket broadcast |
| FR-04: Satellite Analysis | SatEye: daily GEE/Sentinel analysis, risk zone GeoJSON |
| FR-05: Weather Intelligence | WeatherMind: 15-min OpenWeather + IMD ingestion |
| FR-06: Emergency Response | CrisisCommand: LLM action plan ≤60s, 7 agencies contacted |
| FR-07: Infrastructure Health | TrackWatch: composite health score, work orders, 6h refresh |
| FR-08: Cargo Logistics | CargoFlow: wagon tracking, RouteOptima (Dijkstra/DP) |
| FR-09: National Risk Index | Orchestrator: composite NRI, 5-min refresh |
| Non-functional: Security | JWT + TOTP MFA + RBAC (5 roles) + audit log |
| Non-functional: Performance | <200ms API p99, <500ms WS latency |

## License

Proprietary — Ministry of Railways, Government of India.
