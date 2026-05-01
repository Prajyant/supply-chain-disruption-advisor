"""API routes for the supply chain disruption advisor."""
# Auth disabled - all endpoints are public (2026-05-01)
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, status

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    IngestRequest,
    IngestResponse,
    RiskAssessment,
    ShipmentRiskRequest,
    ShipmentRiskResponse,
    ShipmentRiskAdviceRequest,
    ShipmentRiskAdviceResponse,
    StrandsShipmentRiskRequest,
    StrandsShipmentRiskResponse,
)
from app.services.advisor_service import AdvisorService
from app.services.gemini_advice_service import GeminiAdviceService
from app.services.graph_service import GraphService
from app.services.shipment_risk_service import ShipmentRiskService
from app.services.strands_orchestrator_service import StrandsOrchestratorService
from app.ingestion.vessel_tracker import VesselTrackerClient
from app.agents.supply_chain_agent import is_strands_available
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()
advisor_service = AdvisorService()
graph_service = GraphService()
shipment_risk_service = ShipmentRiskService()
gemini_advice_service = GeminiAdviceService()
strands_orchestrator_service = StrandsOrchestratorService()

# Load sample graph
graph_service.load_sample_graph()


# ==================== INGESTION ENDPOINTS ====================


@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> IngestResponse:
    """Ingest data from multiple sources.

    Args:
        req: Ingestion request

    Returns:
        Ingestion response with statistics
    """
    try:
        return advisor_service.ingest(
            supplier_emails_path=req.supplier_emails_path,
            news_feed_path=req.news_feed_path,
            inventory_path=req.inventory_path,
            use_realtime_news=req.use_realtime_news,
            use_live_emails=req.use_live_emails,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to ingest data: {exc}") from exc


# ==================== RISK ENDPOINTS ====================


@router.get("/risks", response_model=list[RiskAssessment])
def risks() -> list[RiskAssessment]:
    """Get all risk assessments.

    Returns:
        List of risk assessments
    """
    return advisor_service.get_risks()


@router.get("/risks/{risk_id}", response_model=RiskAssessment)
def get_risk(risk_id: str) -> RiskAssessment:
    """Get a specific risk by ID.

    Args:
        risk_id: The risk ID

    Returns:
        Risk assessment

    Raises:
        HTTPException: If risk not found
    """
    risks = advisor_service.get_risks()
    for risk in risks:
        if risk.get("risk_id") == risk_id:
            return risk

    raise HTTPException(status_code=404, detail="Risk not found")


@router.get("/vessels/{imo_number}")
def get_vessel_by_imo(imo_number: str) -> dict:
    """Fetch vessel telemetry by IMO number."""
    vessel = VesselTrackerClient().get_vessel_by_imo(imo_number)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"No vessel found for IMO {imo_number}")
    return vessel


@router.post("/shipments/risk-score", response_model=ShipmentRiskResponse)
def score_shipment_risk(req: ShipmentRiskRequest) -> ShipmentRiskResponse:
    """Score a shipment using XGBoost when available, otherwise heuristic features."""
    result = shipment_risk_service.score_shipment(
        shipment=req.shipment,
        intelligence_events=req.intelligence_events,
        use_live_intelligence=req.use_live_intelligence,
    )
    return ShipmentRiskResponse(**result)


@router.post("/shipments/risk-advice", response_model=ShipmentRiskAdviceResponse)
def advise_shipment_risk(req: ShipmentRiskAdviceRequest) -> ShipmentRiskAdviceResponse:
    """Score a shipment and return Gemini-formatted mitigation advice."""
    score_result = shipment_risk_service.score_shipment(
        shipment=req.shipment,
        intelligence_events=req.intelligence_events,
        use_live_intelligence=req.use_live_intelligence,
    )
    return gemini_advice_service.build_advice(
        shipment=req.shipment,
        score_result=score_result,
        question=req.question,
    )


@router.post("/agents/strands/shipment-risk", response_model=StrandsShipmentRiskResponse)
def run_strands_shipment_risk_agent(req: StrandsShipmentRiskRequest) -> StrandsShipmentRiskResponse:
    """Run the Strands-orchestrated shipment risk workflow."""
    return strands_orchestrator_service.run_shipment_risk_workflow(req)


@router.get("/agents/strands/status")
def strands_status() -> dict:
    """Return whether the backend process can access the Strands SDK."""
    return {
        "agent": "SupplyChainRiskAgent",
        "strands_sdk_available": is_strands_available(),
    }


# ==================== CHAT ENDPOINTS ====================


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Query the AI advisor with a question.

    Args:
        req: Chat request

    Returns:
        Chat response with answer and context

    Raises:
        HTTPException: If question is empty
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    return advisor_service.chat(question=req.question, top_k=req.top_k)


# ==================== NETWORK/GRAPH ENDPOINTS ====================


@router.get("/network")
def get_network() -> dict:
    """Get the full supply chain network graph.

    Returns:
        Network graph with nodes and edges
    """
    return graph_service.get_network()


@router.get("/node/{node_id}")
def get_node(node_id: str) -> Optional[dict]:
    """Get details for a specific node.

    Args:
        node_id: The node ID

    Returns:
        Node details or None
    """
    return graph_service.get_node(node_id)


@router.get("/node/{node_id}/impact")
def get_node_impact(node_id: str) -> dict:
    """Get upstream and downstream impact for a node.

    Args:
        node_id: The node ID

    Returns:
        Impact analysis with upstream and downstream nodes
    """
    return graph_service.get_node_impact(node_id)


@router.post("/graph/propagate")
def propagate_risk() -> dict:
    """Trigger risk propagation through the graph.

    Returns:
        Propagation results
    """
    return graph_service.propagate_risk()


# ==================== WEBSOCKET ENDPOINTS ====================


@router.websocket("/ws/{subscription}")
async def websocket_endpoint(websocket: WebSocket, subscription: str) -> None:
    """WebSocket endpoint for real-time updates.

    Args:
        websocket: The WebSocket connection
        subscription: The subscription type ("risks", "network", "alerts", "all")
    """
    await manager.connect(websocket, subscription)

    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_json()
            logger.info(f"Received WebSocket message: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ==================== HEALTH ENDPOINT ====================


@router.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Status dictionary
    """
    return {"status": "ok"}
