"""Main FastAPI application for Supply Chain Disruption Advisor."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.api.routes import router
from app.api.vessel_routes import vessel_router
from app.background.workers import WorkerManager, IngestionWorker, RiskWorker, PropagationWorker
from app.ingestion.ais.vessel_worker import get_vessel_worker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global worker manager
worker_manager = WorkerManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - start/stop background workers.

    Args:
        app: The FastAPI application

    Yields:
        None
    """
    # Startup
    logger.info("Starting background workers...")
    from app.api.routes import (
        get_ingestion_service,
        get_risk_service,
        get_graph_service,
    )

    ingestion_svc = get_ingestion_service()
    risk_svc = get_risk_service()
    graph_svc = get_graph_service()

    worker_manager.register_worker("ingestion", IngestionWorker(interval_seconds=900, ingestion_service=ingestion_svc, graph_service=graph_svc))  # 15 min
    worker_manager.register_worker("risk", RiskWorker(interval_seconds=1800, risk_service=risk_svc))  # 30 min
    worker_manager.register_worker("propagation", PropagationWorker(interval_seconds=60, graph_service=graph_svc))  # 1 min

    # Run initial data ingestion immediately so chat works from the start
    logger.info("Running initial data ingestion...")
    ingestion_worker = worker_manager.workers.get("ingestion")
    if ingestion_worker:
        try:
            await ingestion_worker.run()
            logger.info("Initial data ingestion complete — chat advisor ready")
        except Exception as exc:
            logger.warning("Initial ingestion failed (will retry on schedule): %s", exc)

    await worker_manager.start_all()
    logger.info("Background workers started")

    # Start vessel tracking worker
    vessel_worker = get_vessel_worker()
    vessel_worker.initialize()
    await vessel_worker.start()
    logger.info("Vessel tracking worker started")

    yield

    # Shutdown
    logger.info("Stopping background workers...")
    await vessel_worker.stop()
    await worker_manager.stop_all()
    logger.info("Background workers stopped")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Supply Chain Disruption Advisor",
    version="1.0.0",
    description="Real-time supply chain disruption detection and mitigation system",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
# vessel_router first so /vessels/watchlist, /vessels/search etc. match before
# the catch-all /vessels/{imo_number} in the main router
app.include_router(vessel_router)
app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Welcome message
    """
    return {
        "message": "Supply Chain Disruption Advisor API",
        "version": "1.0.0",
        "docs": "/docs",
    }
