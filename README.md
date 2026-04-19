# Supply Chain Disruption Advisor

An AI-assisted MVP that ingests supplier signals, detects disruption risks, and recommends mitigation actions.

## What this does
- Ingests supplier emails, news feed entries, and inventory/order data from CSV files.
- Builds a lightweight retrieval layer (TF-IDF semantic lookup).
- Classifies disruption severity (`low`, `medium`, `high`, `critical`) with clear risk signals.
- Generates actionable mitigation recommendations.
- Exposes APIs via FastAPI and a dashboard/chat UI via Streamlit.

## Project structure
- `app/main.py` - FastAPI app entrypoint
- `app/services/advisor_service.py` - orchestration service
- `app/services/risk_engine.py` - risk detection + recommendations
- `app/retrieval/index.py` - retrieval index and context lookup
- `streamlit_app.py` - dashboard and chat interface
- `data/*.csv` - sample datasets for demo
- `tests/` - basic validation tests

## Quickstart
1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Optional: configure `.env` from `.env.example` for OpenAI-backed analysis.

3. Start backend:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. Start dashboard in a new terminal:

   ```bash
   streamlit run streamlit_app.py
   ```

5. In the dashboard, click **Ingest Sample Data**, then explore risks and chat.

## API endpoints
- `GET /health` - service health
- `POST /ingest` - load datasets and build index
- `GET /risks` - list latest risk assessments
- `POST /chat` - conversational query over indexed context

## Notes
- Works fully in deterministic heuristic mode without API keys.
- If `OPENAI_API_KEY` is configured, the analyzer attempts LLM enrichment and safely falls back on heuristic mode if LLM call fails.
