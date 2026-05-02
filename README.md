# Supply Chain Disruption Advisor

An AI-assisted MVP that ingests supplier signals, detects disruption risks, and recommends mitigation actions with real-time digital twin visualization.

## Features

- **Risk Monitoring**: Ingest supplier emails, news feeds, and inventory data
- **Digital Twin**: Visualize supply chain network with impact propagation
- **Real-Time Updates**: WebSocket-based live risk notifications
- **AI Advisory**: RAG-grounded responses using LangChain and Gemini
- **Authentication**: JWT-based auth with role-based access control (RBAC)
- **Background Jobs**: Automated ingestion, risk analysis, and propagation

## Architecture

### Backend
```
app/
 ├── api/              # REST endpoints
 ├── auth/             # JWT + RBAC
 ├── background/       # Background job workers
 ├── graph/            # Digital twin network model
 ├── ingestion/        # Data loaders
 ├── models/           # Pydantic schemas
 ├── retrieval/        # Vector search index
 ├── services/         # Service layer
 ├── websocket/        # Real-time updates
 └── main.py           # FastAPI entrypoint
```

### Frontend
```
frontend/
 ├── src/
 │   ├── components/  # Reusable UI components
 │   ├── pages/        # Page components
 │   ├── services/     # API client
 │   ├── store/        # State management
 │   └── types/        # TypeScript types
 └── public/           # Static assets
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
python --version  # use Python 3.13
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

### Option 3: Streamlit Dashboard (Legacy)

```bash
streamlit run streamlit_app.py
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
OPENAI_API_KEY=your-openai-api-key-here
GOOGLE_API_KEY=your-google-api-key-here
JWT_SECRET=your-secret-key-change-in-production
```

## API Endpoints

### Authentication
- `POST /auth/login` - Login and get tokens
- `POST /auth/refresh` - Refresh access token

### Ingestion
- `POST /ingest` - Load data and build indexes

### Risks
- `GET /risks` - List all risk assessments
- `GET /risks/{id}` - Get specific risk details

### Network
- `GET /network` - Get supply chain graph
- `GET /node/{id}` - Get node details
- `GET /node/{id}/impact` - Get upstream/downstream impact
- `POST /graph/propagate` - Trigger risk propagation

### Chat
- `POST /chat` - Query AI advisor

### WebSocket
- `WS /ws/{subscription}` - Real-time updates (risks, network, alerts)

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
