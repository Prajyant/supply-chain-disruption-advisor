"""API routes for the supply chain disruption advisor."""
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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
from app.auth.jwt_handler import JWTHandler
from app.auth.rbac import authenticate_user
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

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Validate JWT and return current user.

    If no token is provided, returns a default admin user so the app
    can operate without authentication during development.
    """
    if credentials is None:
        return {"id": "1", "username": "admin", "role": "admin"}

    payload = JWTHandler.verify_token(credentials.credentials, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return {"id": payload.get("sub", ""), "username": payload.get("username", ""), "role": payload.get("role", "viewer")}


# ==================== AUTH ENDPOINTS ====================


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(req: LoginRequest) -> dict:
    """Authenticate user and return JWT tokens."""
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token_data = {"sub": user["id"], "username": user["username"], "role": user["role"].value}
    access_token = JWTHandler.create_access_token(token_data)
    refresh_token = JWTHandler.create_refresh_token(token_data)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user["id"], "username": user["username"], "role": user["role"].value},
    }


@router.post("/auth/refresh")
def refresh_token(refresh_token: str) -> dict:
    """Refresh an access token using a valid refresh token."""
    payload = JWTHandler.verify_token(refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    token_data = {"sub": payload["sub"], "username": payload["username"], "role": payload["role"]}
    new_access = JWTHandler.create_access_token(token_data)
    return {"access_token": new_access}


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


# ==================== NODE CONTEXT ENDPOINTS (Phase 3) ====================


@router.get("/node/{node_id}/context")
def get_node_context(node_id: str) -> dict:
    """Get full enriched context ('knowledge card') for a node.

    Called on node click — returns shipments, orders, risk history, news.

    Args:
        node_id: The node ID

    Returns:
        Full NodeContext dictionary

    Raises:
        HTTPException: If node not found
    """
    context = advisor_service.get_node_context(node_id)
    if not context:
        raise HTTPException(status_code=404, detail="Node not found")
    return context


# ==================== SHIPMENT TRACKER ENDPOINTS (Phase 3) ====================


@router.get("/shipments")
def get_shipments() -> list[dict]:
    """Get all tracked shipments.

    Returns:
        List of shipment dictionaries
    """
    return advisor_service.get_shipments()


@router.get("/shipments/node/{node_id}")
def get_shipments_for_node(node_id: str) -> list[dict]:
    """Get all shipments for a specific node.

    Args:
        node_id: The node ID

    Returns:
        List of shipment dictionaries for this node
    """
    return advisor_service.get_shipments_for_node(node_id)


# ==================== PLAYBOOK ENDPOINTS (Phase 3) ====================


@router.get("/playbooks")
def get_playbooks() -> dict:
    """List all playbook definitions with acceptance rates."""
    playbooks = advisor_service.playbook_engine.get_playbooks()
    return {"playbooks": [pb.model_dump() for pb in playbooks]}


@router.get("/playbooks/executions")
def get_playbook_executions() -> dict:
    """List all triggered playbook executions, most recent first."""
    executions = advisor_service.playbook_engine.get_executions()
    return {"executions": [e.model_dump() for e in executions]}


@router.patch("/playbooks/{playbook_id}")
async def toggle_playbook(playbook_id: str, enabled: bool = True) -> dict:
    """Toggle a playbook's enabled/disabled state."""
    playbook = await advisor_service.playbook_engine.toggle_playbook(playbook_id, enabled)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return {
        "id": playbook.id,
        "name": playbook.name,
        "enabled": playbook.enabled,
        "warning": "Setting is in-memory only. Will reset on server restart.",
    }


@router.post("/playbooks/executions/{execution_id}/feedback")
def submit_playbook_feedback(
    execution_id: str,
    decision: str,
    comment: Optional[str] = None,
) -> dict:
    """Submit feedback (accept/reject) on a playbook execution."""
    execution = advisor_service.playbook_engine.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if decision not in ("accepted", "rejected", "partial"):
        raise HTTPException(status_code=400, detail="Decision must be: accepted, rejected, or partial")

    from app.models.feedback import ContextSnapshot
    ctx = ContextSnapshot(
        node_id=execution.node_id,
        risk_score=0.0,
        severity=execution.severity,
        disruption_type=execution.disruption_type,
    )

    result = advisor_service.feedback_service.record_feedback(
        execution_id=execution_id,
        playbook_id=execution.playbook_id,
        decision=decision,
        user_id="admin",
        comment=comment,
        context=ctx,
    )

    if not result:
        raise HTTPException(status_code=409, detail="Feedback already exists for this execution")

    return {"status": "ok", "feedback_id": result.id}


@router.post("/playbooks/{playbook_id}/simulate")
def simulate_playbook(playbook_id: str) -> dict:
    """Simulate a playbook execution for testing."""
    result = advisor_service.playbook_engine.simulate(playbook_id)
    if not result:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return result


# ==================== FEEDBACK ENDPOINTS (Phase 3) ====================


@router.get("/feedback/stats")
def get_feedback_stats() -> dict:
    """Get feedback statistics."""
    return advisor_service.feedback_service.get_stats()


@router.get("/feedback/history")
def get_feedback_history(limit: int = 50) -> dict:
    """Get feedback history."""
    history = advisor_service.feedback_service.get_history(limit=limit)
    return {"history": [h.model_dump() for h in history]}


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
