# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Commands

**Setup**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

**Run backend**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Run dashboard** (separate terminal)
```bash
streamlit run streamlit_app.py
```

**Run tests**
```bash
pytest tests/
```

## Architecture

This is a supply chain disruption detection system with three layers:

**Data Flow:**
1. **Ingestion** (`app/ingestion/loaders.py`) - Loads supplier emails, news feeds, and inventory data from CSVs into normalized event records
2. **Retrieval** (`app/retrieval/index.py`) - TF-IDF vectorizer with cosine similarity for semantic search over event chunks
3. **Risk Analysis** (`app/services/risk_engine.py`) - Classifies disruption severity (low/medium/high/critical) using keyword matching or optional OpenAI LLM enrichment
4. **Orchestration** (`app/services/advisor_service.py`) - Coordinates ingestion, retrieval, and risk analysis; exposes chat interface

**API Layer** (`app/api/routes.py`):
- `POST /ingest` - Load data and build index
- `GET /risks` - Return sorted risk assessments
- `POST /chat` - Answer questions using retrieved context + mitigation recommendations

**Frontend** (`streamlit_app.py`) - Dashboard for data ingestion, risk visualization, and chat interface.

**Key Design:**
- Dual-mode analysis: LLM-backed when `OPENAI_API_KEY` is set, otherwise deterministic heuristics via `SEVERITY_KEYWORDS` and `DISRUPTION_TYPES` mappings in `risk_engine.py`
- Risk recommendations are pre-mapped by severity level in `RECOMMENDATION_MAP`
