# Supply Chain Disruption Advisor

An AI-powered platform that ingests supplier signals, detects disruption risks using predictive cross-referencing, and recommends mitigation actions — with a real-time digital twin, multi-agent debate system, and Bedrock-powered advisory chat.

## Features

- **Predictive Risk Detection**: Cross-references supplier emails with live world news to predict disruptions before they hit
- **Multi-Agent Debate System**: 5 specialized agents (cost, risk, speed, supply chain, digital twin) + orchestrator for balanced decision-making
- **Digital Twin**: Interactive supply chain network graph with risk propagation and node-level context cards
- **AI Chat Advisor**: Bedrock Claude-powered chat with full system awareness (risks, shipments, weather, trade, network)
- **Shipment Tracking**: Real-time shipment status with per-shipment risk scoring and resolution packages
- **Live Intelligence**: Weather monitoring, trade policy tracking, vessel tracking, and flight tracking
- **Automated Playbooks**: Rule-based automation that triggers actions when risk thresholds are crossed
- **Role-Based Dashboards**: Operations view, CFO view, and standard risk dashboard
- **Real-Time Updates**: WebSocket-based live notifications for risks, network changes, and playbook executions
- **Authentication**: JWT + Firebase Auth with role-based access control (RBAC)

## Architecture

### Backend
```
app/
 ├── agents/           # Multi-agent system
 │   ├── base.py              # Base agent class
 │   ├── cost_agent.py        # Cost optimization agent
 │   ├── risk_agent.py        # Risk assessment agent
 │   ├── speed_agent.py       # Delivery speed agent
 │   ├── twin_agent.py        # Digital twin simulation agent
 │   ├── supply_chain_agent.py # Strands-based supply chain agent
 │   └── debate_orchestrator.py # Multi-agent debate coordinator
 ├── api/              # REST + WebSocket endpoints
 ├── auth/             # JWT + Firebase + RBAC
 ├── background/       # Background job workers
 ├── core/             # Configuration
 ├── graph/            # Digital twin network model
 ├── ingestion/        # Data loaders + live intelligence
 │   ├── loaders.py           # CSV data ingestion
 │   ├── weather_monitor.py   # Open-Meteo weather + marine data
 │   ├── trade_monitor.py     # Trade policy event tracking
 │   ├── vessel_tracker.py    # Vessel position tracking (IMO)
 │   ├── flight_tracker.py    # Flight/air cargo tracking
 │   ├── worldmonitor.py      # World news aggregation
 │   └── rss_utils.py         # RSS feed parsing
 ├── models/           # Pydantic schemas + feedback models
 ├── retrieval/        # TF-IDF vector search index
 ├── services/         # Service layer
 │   ├── advisor_service.py          # Master orchestrator
 │   ├── chat_service.py             # Bedrock-powered chat advisor
 │   ├── risk_service.py             # Risk classification engine
 │   ├── risk_engine.py              # Severity scoring (LLM + heuristic)
 │   ├── shipment_risk_service.py    # Per-shipment risk scoring
 │   ├── bedrock_advice_service.py   # Bedrock mitigation advice
 │   ├── resolution_service.py       # Resolution package generation
 │   ├── strands_orchestrator_service.py # Strands SDK workflow
 │   ├── graph_service.py            # Graph operations
 │   ├── shipment_tracker.py         # Shipment lifecycle management
 │   ├── playbook_engine.py          # Automated playbook evaluation
 │   ├── feedback_service.py         # User feedback collection
 │   └── ingestion_service.py        # Ingestion coordination
 ├── websocket/        # Real-time update manager
 └── main.py           # FastAPI entrypoint
```

### Frontend
```
frontend/
 ├── src/
 │   ├── components/
 │   │   ├── GlobalChat.tsx        # Floating AI chat widget
 │   │   ├── VesselMap.tsx         # Interactive vessel map
 │   │   ├── WeatherOverlay.tsx    # Weather visualization
 │   │   ├── RiskCard.tsx          # Risk display cards
 │   │   ├── ResolutionPackage.tsx # Resolution action cards
 │   │   ├── ShipmentTracker.tsx   # Shipment status component
 │   │   ├── NodeDetail.tsx        # Graph node context card
 │   │   ├── RouteLines.tsx        # Route visualization
 │   │   └── ...
 │   ├── pages/
 │   │   ├── Dashboard.tsx         # Main risk dashboard
 │   │   ├── CFODashboard.tsx      # Financial impact view
 │   │   ├── OperationsDashboard.tsx # Operations view
 │   │   ├── DigitalTwin.tsx       # Network graph visualization
 │   │   ├── ShipmentDetail.tsx    # Per-shipment deep dive
 │   │   ├── Chat.tsx              # Full-page chat interface
 │   │   ├── Playbooks.tsx         # Playbook management
 │   │   └── Settings.tsx          # App settings
 │   ├── services/     # API client + data services
 │   ├── store/        # Zustand state management
 │   ├── context/      # React context (view modes)
 │   └── types/        # TypeScript types
 └── public/           # Static assets + demo data
```

## Quickstart

### Option 1: Docker Compose (Recommended)

```bash
docker-compose up
```

Access the app at http://localhost:3000

### Option 2: Manual Setup

**Backend:**
```bash
python --version  # Python 3.13
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Access the app at http://localhost:3000

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# AI/LLM
OPENAI_API_KEY=your-openai-api-key-here
GOOGLE_API_KEY=your-google-api-key-here
GEMINI_API_KEY=your-gemini-api-key

# Amazon Bedrock (powers chat advisor + advice generation)
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_SESSION_TOKEN=your-aws-session-token-if-using-temporary-credentials
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0

# Auth
JWT_SECRET=your-secret-key-change-in-production
FIREBASE_PROJECT_ID=your-firebase-project-id

# Database
DATABASE_URL=sqlite:///./supply_chain.db
```

## API Endpoints

### Authentication
- `POST /auth/login` — Login and get JWT tokens
- `POST /auth/refresh` — Refresh access token

### Ingestion
- `POST /ingest` — Load data, build indexes, run predictive cross-reference

### Risks
- `GET /risks` — All risk assessments (reactive + predictive)
- `GET /risks/{id}` — Specific risk details

### Shipments
- `GET /shipments` — All tracked shipments
- `GET /shipments/node/{node_id}` — Shipments for a node
- `POST /shipments/risk-score` — Score a shipment's risk
- `POST /shipments/risk-advice` — Get Bedrock mitigation advice
- `POST /shipments/resolution-package` — Full resolution package with financial impact
- `POST /shipments/preload` — Background preload all shipment analyses
- `GET /shipments/{id}/preloaded` — Get cached analysis

### Agents
- `POST /agents/strands/shipment-risk` — Run Strands-orchestrated risk workflow
- `GET /agents/strands/status` — Check Strands SDK availability

### Network / Digital Twin
- `GET /network` — Full supply chain graph
- `GET /node/{id}` — Node details
- `GET /node/{id}/context` — Full enriched node context (shipments, orders, risks, news)
- `GET /node/{id}/impact` — Upstream/downstream impact analysis
- `POST /graph/propagate` — Trigger risk propagation
- `POST /graph/score-nodes` — Score nodes using live intelligence

### Chat
- `POST /chat` — Query AI advisor (Bedrock-powered with full system context)
- `GET /chat/context` — Current advisor knowledge state

### Playbooks
- `GET /playbooks` — List playbook definitions
- `GET /playbooks/executions` — List triggered executions
- `PATCH /playbooks/{id}` — Toggle playbook enabled/disabled
- `POST /playbooks/{id}/simulate` — Simulate a playbook execution
- `POST /playbooks/executions/{id}/feedback` — Submit accept/reject feedback

### Weather
- `GET /weather/route?points=lat,lon;lat,lon` — Weather along a route
- `GET /weather/position?lat=...&lon=...` — Weather + marine at a point

### Vessels
- `GET /vessels/{imo_number}` — Vessel telemetry by IMO

### Feedback
- `GET /feedback/stats` — Feedback statistics
- `GET /feedback/history` — Feedback history

### WebSocket
- `WS /ws/{subscription}` — Real-time updates (risks, network, alerts, all)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.13 |
| AI/LLM | Amazon Bedrock (Claude), Google Gemini, OpenAI |
| Agent Framework | Strands Agents SDK |
| Frontend | React, TypeScript, Vite, TailwindCSS |
| State | Zustand, React Query |
| Maps | Leaflet |
| Auth | JWT + Firebase Admin |
| Search | TF-IDF + cosine similarity |
| ML | XGBoost (shipment risk scoring) |
| Real-time | WebSockets |

## Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | password | admin |
| buyer | password | buyer |
| viewer | password | viewer |

## Testing

```bash
pytest tests/
```

## Deployment

### Production Stack
- Backend: AWS ECS or GCP Cloud Run
- Frontend: Vercel or Netlify
- Database: PostgreSQL
- Vector DB: Pinecone or hosted FAISS
- Cache: Redis
- Message Queue: Kafka or RabbitMQ

## License

MIT
