# Supply Chain Disruption Advisor MVP Design

**Date:** 2026-04-24
**Status:** Approved
**Version:** 1.0

## Overview

This document describes the MVP design for the Supply Chain Disruption Advisor system. The MVP focuses on core risk monitoring, digital twin visualization with impact propagation, real-time updates via WebSockets, and basic security.

## Architecture

### Backend Structure

```
app/
 ├── ingestion/          # Data loaders (emails, news, inventory)
 ├── risk_engine/        # Risk classification and scoring
 ├── rag/               # Retrieval + LLM (LangChain/Bedrock/FAISS)
 ├── graph/             # Digital twin - network model and propagation
 ├── services/          # Service layer - orchestrates modules
 │   ├── ingestion_service.py
 │   ├── risk_service.py
 │   ├── chat_service.py
 │   └── graph_service.py
 ├── background/        # Background job workers
 │   ├── ingestion_worker.py
 │   ├── risk_worker.py
 │   └── propagation_worker.py
 ├── websocket/         # Real-time updates
 │   └── manager.py
 ├── auth/             # JWT + RBAC
 │   ├── jwt_handler.py
 │   └── rbac.py
 ├── api/              # REST endpoints (no business logic)
 └── models/           # Pydantic schemas
```

### Frontend Structure

```
frontend/
 ├── src/
 │   ├── components/    # Reusable UI components
 │   ├── pages/        # Page components
 │   │   ├── Dashboard.tsx
 │   │   ├── DigitalTwin.tsx
 │   │   ├── ChatAdvisor.tsx
 │   │   └── Settings.tsx
 │   ├── hooks/        # Custom React hooks
 │   ├── services/     # API client
 │   ├── store/        # State management
 │   └── types/        # TypeScript types
 └── public/           # Static assets
```

## Core Features

### 1. Risk Monitoring

**Functionality:**
- Ingest supplier emails, news feeds, inventory data
- Classify disruption severity (Low/Medium/High/Critical)
- Multi-factor scoring (delay + supplier importance + inventory level)

**API Endpoints:**
- `POST /ingest` - Load data and build indexes
- `GET /risks` - Return sorted risk assessments
- `GET /risks/{id}` - Get specific risk details

### 2. Digital Twin Visualization

**Graph Schema:**
```
Node Types:
- supplier: {id, name, location, risk_score, status, criticality}
- warehouse: {id, name, location, capacity, current_stock, risk_score}
- plant: {id, name, location, production_capacity, risk_score}

Edge Types:
- supplies_to: {from, to, material_type, volume, lead_time}
- ships_to: {from, to, route, transit_time}
```

**API Endpoints:**
- `GET /network` - Return full supply chain graph
- `GET /node/{id}` - Return node details with risk status
- `POST /graph/propagate` - Trigger risk propagation
- `GET /node/{id}/impact` - Get upstream/downstream impact

### 3. Impact Propagation

**Algorithm:**
```
For each edge (A → B):
  if A.risk_score > threshold:
    B.derived_risk += A.risk_score * edge.weight * propagation_factor

Node.final_risk = max(node.direct_risk, node.derived_risk)
```

**Propagation Factors:**
- `edge.weight`: 0.1-1.0 based on material volume/criticality
- `propagation_factor`: 0.3 (configurable)
- `threshold`: 0.6 (configurable)

### 4. Real-Time Updates (WebSockets)

**Event Types:**
```typescript
// Client → Server
subscribe_risks()
subscribe_network()
subscribe_alerts()

// Server → Client
risk_updated {risk_id, severity, node_id}
node_status_changed {node_id, status, risk_score}
new_alert {alert_id, severity, message}
ingestion_complete {events_count, risks_count}
```

### 5. AI Advisory System

**Functionality:**
- RAG-grounded responses using LangChain
- Bedrock LLM for reasoning
- FAISS for semantic search
- Mitigation recommendations

**API Endpoints:**
- `POST /chat` - Query with retrieved context

### 6. Security

**Authentication:**
- JWT tokens (15 min access, 7 day refresh)
- Login endpoint: `POST /auth/login`

**Role-Based Access Control:**

| Role | Ingest | View Risks | Chat | Graph | Settings |
|------|--------|------------|------|-------|----------|
| admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| manager | ✅ | ✅ | ✅ | ✅ | ❌ |
| viewer | ❌ | ✅ | ✅ | ✅ | ❌ |

## Background Jobs

### Ingestion Worker
- Periodically fetches real-time news from RSS feeds
- Runs every 15 minutes (configurable)
- Pushes updates via WebSocket

### Risk Worker
- Re-analyses events on schedule
- Updates risk scores
- Runs every 30 minutes (configurable)

### Propagation Worker
- Updates derived risks through graph
- Runs on risk score changes
- Pushes node status updates via WebSocket

## Technology Stack

### Backend
- **Framework:** FastAPI
- **LLM:** Amazon Bedrock (Claude)
- **Vector DB:** FAISS
- **Auth:** JWT + Pydantic
- **Background Jobs:** Celery or asyncio tasks
- **WebSockets:** FastAPI WebSocket support

### Frontend
- **Framework:** React + Vite
- **Language:** TypeScript
- **State:** React Query
- **Graph:** D3.js or React Flow
- **Styling:** Tailwind CSS
- **WebSocket:** Native WebSocket API

### Data Storage
- **Structured:** SQLite (MVP), PostgreSQL (production)
- **Vector:** FAISS (local)
- **Cache:** In-memory (MVP), Redis (production)

## API Contracts

### Authentication
```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}

Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": "1",
    "username": "admin",
    "role": "admin"
  }
}
```

### Ingestion
```http
POST /ingest
Authorization: Bearer <token>
Content-Type: application/json

{
  "supplier_emails_path": "data/supplier_emails.csv",
  "news_feed_path": "data/news_feed.csv",
  "inventory_path": "data/inventory.csv",
  "use_realtime_news": true
}

Response:
{
  "ingested_events": 150,
  "indexed_chunks": 450,
  "message": "Real-time data fetched from WorldMonitor API."
}
```

### Risks
```http
GET /risks
Authorization: Bearer <token>

Response:
[
  {
    "risk_id": "risk_001",
    "source": "news_feed",
    "reference_id": "news_123",
    "detected_at": "2026-04-24T10:30:00Z",
    "disruption_type": "logistics_delay",
    "severity": "high",
    "confidence": 0.85,
    "signals": ["port_congestion", "shipping_delay"],
    "recommendations": ["divert_to_alternative_port", "increase_safety_stock"],
    "summary": "Port congestion causing shipping delays",
    "headline": "Major Port Congestion Disrupts Supply Chain",
    "metadata": {}
  }
]
```

### Network
```http
GET /network
Authorization: Bearer <token>

Response:
{
  "nodes": [
    {
      "id": "supplier_001",
      "type": "supplier",
      "name": "Acme Parts",
      "location": "Shanghai, China",
      "risk_score": 0.75,
      "status": "at_risk",
      "criticality": "high"
    }
  ],
  "edges": [
    {
      "from": "supplier_001",
      "to": "warehouse_001",
      "type": "supplies_to",
      "material_type": "electronics",
      "volume": 1000,
      "lead_time": 14
    }
  ],
  "metadata": {
    "last_updated": "2026-04-24T10:30:00Z",
    "total_risks": 25
  }
}
```

### Chat
```http
POST /chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "question": "Which suppliers are risky this week?",
  "top_k": 5
}

Response:
{
  "answer": "Based on recent data, 3 suppliers are at high risk...",
  "supporting_context": [...],
  "recommendations": [...]
}
```

## Implementation Phases

### Phase 1: Backend Refactoring (Week 1)
- Add service layer
- Implement background job framework
- Add WebSocket manager
- Implement JWT + RBAC
- Add impact propagation logic
- Refactor existing code into module structure

### Phase 2: React Frontend Core (Week 1-2)
- Set up React + Vite with TypeScript
- Build Dashboard with real-time updates
- Build Chat Advisor
- Implement authentication flow
- Connect to existing APIs

### Phase 3: Digital Twin + Propagation (Week 2-3)
- Build graph visualization with D3.js/React Flow
- Implement node detail views
- Add impact propagation visualization
- Connect WebSocket for live updates

### Phase 4: Streamlit Removal (Week 3)
- Validate React feature parity
- Remove Streamlit dependencies
- Final testing and cleanup

## Deployment

### Docker Compose (MVP)
```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./supply_chain.db
      - JWT_SECRET=${JWT_SECRET}

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
```

### Production (Future)
- Backend: AWS ECS or GCP Cloud Run
- Frontend: Vercel or Netlify
- Database: AWS RDS PostgreSQL
- Vector DB: Hosted FAISS or Pinecone
- Cache: Redis
- Message Queue: Kafka or RabbitMQ

## Non-Functional Requirements

### Performance
- Dashboard queries: < 2 seconds
- Chat responses: < 5 seconds
- WebSocket latency: < 100ms

### Scalability
- Support 10,000+ suppliers
- Handle 100+ concurrent users
- Horizontal scaling for background workers

### Security
- JWT authentication for all endpoints
- RBAC for role-based access
- Encrypted data at rest
- API rate limiting

### Availability
- 99.9% uptime target
- Graceful degradation on failures
- Automatic retry for transient errors

## Testing Strategy

### Backend Tests
- Unit tests for all services
- Integration tests for API endpoints
- WebSocket connection tests
- Background job tests

### Frontend Tests
- Component tests with React Testing Library
- E2E tests with Playwright
- API integration tests

### Manual Testing
- Risk detection accuracy validation
- Graph visualization correctness
- Real-time update verification
- Authentication flow testing

## Success Criteria

1. **Functional**
   - All core features working as specified
   - Real-time updates via WebSocket
   - Impact propagation visible in graph
   - Authentication and RBAC enforced

2. **Performance**
   - Dashboard loads in < 2 seconds
   - Chat responds in < 5 seconds
   - Graph renders smoothly with 100+ nodes

3. **User Experience**
   - Intuitive dashboard layout
   - Clear risk visualization
   - Responsive design for desktop/tablet

4. **Code Quality**
   - Clean module separation
   - No UI logic in backend
   - Type-safe API contracts
   - Comprehensive test coverage
