"""API routes for the supply chain disruption advisor."""
import asyncio
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect, status, UploadFile, File
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
    ResolutionPackage,
)
from app.services.advisor_service import AdvisorService
from app.services.bedrock_advice_service import BedrockAdviceService
from app.services.graph_service import GraphService
from app.services.ingestion_service import IngestionService
from app.services.risk_service import RiskService
from app.services.shipment_risk_service import ShipmentRiskService
from app.services.strands_orchestrator_service import StrandsOrchestratorService
from app.ingestion.vessel_tracker import VesselTrackerClient
from app.ingestion.weather_monitor import fetch_weather_for_points
from app.agents.supply_chain_agent import is_strands_available
from app.auth.jwt_handler import JWTHandler
from app.auth.rbac import authenticate_user
from functools import lru_cache
from app.services.chat_service import ChatService
from app.services.playbook_engine import PlaybookEngine
from app.services.feedback_service import FeedbackService
from app.services.shipment_tracker import ShipmentTracker

from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== DEPENDENCIES ====================

@lru_cache(maxsize=1)
def get_risk_service() -> RiskService:
    return RiskService()

@lru_cache(maxsize=1)
def get_ingestion_service() -> IngestionService:
    return IngestionService()

@lru_cache(maxsize=1)
def get_graph_service() -> GraphService:
    svc = GraphService()
    svc.load_sample_graph()
    return svc

@lru_cache(maxsize=1)
def get_shipment_risk_service() -> ShipmentRiskService:
    return ShipmentRiskService()

@lru_cache(maxsize=1)
def get_bedrock_advice_service() -> BedrockAdviceService:
    return BedrockAdviceService()

@lru_cache(maxsize=1)
def get_shipment_tracker() -> ShipmentTracker:
    return ShipmentTracker()

@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    return ChatService()

@lru_cache(maxsize=1)
def get_playbook_engine() -> PlaybookEngine:
    return PlaybookEngine()

@lru_cache(maxsize=1)
def get_feedback_service() -> FeedbackService:
    return FeedbackService()

@lru_cache(maxsize=1)
def get_strands_orchestrator_service() -> StrandsOrchestratorService:
    return StrandsOrchestratorService()

@lru_cache(maxsize=1)
def get_advisor_service() -> AdvisorService:
    return AdvisorService(
        ingestion_service=get_ingestion_service(),
        risk_service=get_risk_service(),
        chat_service=get_chat_service(),
        graph_service=get_graph_service(),
        shipment_tracker=get_shipment_tracker(),
        playbook_engine=get_playbook_engine(),
        feedback_service=get_feedback_service(),
    )

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
def ingest(
    req: IngestRequest,
    advisor_service: AdvisorService = Depends(get_advisor_service)
) -> IngestResponse:
    """Ingest data from multiple sources.

    Args:
        req: Ingestion request
        advisor_service: Advisor service

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
def risks(advisor_service: AdvisorService = Depends(get_advisor_service)) -> list[RiskAssessment]:
    """Get all risk assessments.

    Returns:
        List of risk assessments
    """
    return advisor_service.get_risks()


@router.get("/risks/{risk_id}", response_model=RiskAssessment)
def get_risk(
    risk_id: str,
    advisor_service: AdvisorService = Depends(get_advisor_service)
) -> RiskAssessment:
    """Get a specific risk by ID.

    Args:
        risk_id: The risk ID
        advisor_service: Advisor service

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
async def get_vessel_by_imo(imo_number: str) -> dict:
    """Fetch vessel telemetry by IMO number."""
    client = VesselTrackerClient()
    vessel = await asyncio.to_thread(client.get_vessel_by_imo, imo_number)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"No vessel found for IMO {imo_number}")
    return vessel


@router.post("/shipments/upload-csv")
async def upload_shipments_csv(file: UploadFile = File(...)) -> dict:
    """Upload a CSV file with shipment data.

    Parses the CSV and returns structured shipment objects that the frontend
    can use for risk analysis and vessel tracking.
    """
    import csv
    import io

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    try:
        content = await file.read()
        text = content.decode("utf-8-sig")  # Handle BOM from Excel
        reader = csv.DictReader(io.StringIO(text))

        shipments = []
        for row in reader:
            # Skip empty rows
            if not any(row.values()):
                continue

            def safe_float(val):
                try:
                    return float(val) if val and val.strip() else None
                except (ValueError, TypeError):
                    return None

            def safe_int(val):
                try:
                    return int(float(val)) if val and val.strip() else 0
                except (ValueError, TypeError):
                    return 0

            imo = (row.get("imo_number") or "").strip()
            lat = safe_float(row.get("vessel_latitude"))
            lon = safe_float(row.get("vessel_longitude"))

            shipment = {
                "shipment_id": (row.get("shipment_id") or f"SHP-{len(shipments)+1:04d}").strip(),
                "supplier": (row.get("supplier") or "Unknown").strip(),
                "origin": (row.get("origin") or "").strip(),
                "destination": (row.get("destination") or "").strip(),
                "route_nodes": [n.strip() for n in (row.get("route_nodes") or "").split("|") if n.strip()],
                "imo_number": imo or None,
                "mmsi": (row.get("mmsi") or "").strip() or None,
                "vessel_name": (row.get("vessel_name") or "").strip() or None,
                "vessel_latitude": lat,
                "vessel_longitude": lon,
                "vessel_status": (row.get("vessel_status") or "").strip() or None,
                "vessel_speed_knots": safe_float(row.get("vessel_speed_knots")),
                "vessel_course_degrees": safe_float(row.get("vessel_course_degrees")),
                "vessel_progress_percent": safe_float(row.get("vessel_progress_percent")),
                "transport_mode": "sea",
                "material": (row.get("material") or "general cargo").strip(),
                "quantity": safe_float(row.get("quantity")) or 0,
                "lead_time_days": safe_float(row.get("lead_time_days")) or 0,
                "inventory_days_cover": safe_float(row.get("inventory_days_cover")) or 0,
                "supplier_delay_count": safe_int(row.get("supplier_delay_count")),
                "priority": (row.get("priority") or "1").strip(),
                "declared_value_usd": safe_float(row.get("declared_value_usd")) or 0,
                "departure_date": (row.get("departure_date") or "").strip() or None,
                "eta_date": (row.get("eta_date") or "").strip() or None,
            }
            shipments.append(shipment)

        logger.info(f"CSV upload: parsed {len(shipments)} shipments from {file.filename}")
        return {
            "shipments": shipments,
            "count": len(shipments),
            "filename": file.filename,
        }
    except Exception as e:
        logger.error(f"CSV upload failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")


@router.post("/shipments/risk-score", response_model=ShipmentRiskResponse)
def score_shipment_risk(
    req: ShipmentRiskRequest,
    shipment_risk_service: ShipmentRiskService = Depends(get_shipment_risk_service)
) -> ShipmentRiskResponse:
    """Score a shipment using XGBoost when available, otherwise heuristic features."""
    result = shipment_risk_service.score_shipment(
        shipment=req.shipment,
        intelligence_events=req.intelligence_events,
        use_live_intelligence=req.use_live_intelligence,
    )
    return ShipmentRiskResponse(**result)


@router.post("/shipments/risk-advice", response_model=ShipmentRiskAdviceResponse)
def advise_shipment_risk(
    req: ShipmentRiskAdviceRequest,
    shipment_risk_service: ShipmentRiskService = Depends(get_shipment_risk_service),
    bedrock_advice_service: BedrockAdviceService = Depends(get_bedrock_advice_service)
) -> ShipmentRiskAdviceResponse:
    """Score a shipment and return Bedrock-formatted mitigation advice."""
    score_result = shipment_risk_service.score_shipment(
        shipment=req.shipment,
        intelligence_events=req.intelligence_events,
        use_live_intelligence=req.use_live_intelligence,
    )
    return bedrock_advice_service.build_advice(
        shipment=req.shipment,
        score_result=score_result,
        question=req.question,
    )


def get_resolution_service() -> "ResolutionService":
    from app.services.resolution_service import ResolutionService
    return ResolutionService()


@router.post("/shipments/resolution-package", response_model=ResolutionPackage)
def generate_resolution_package(
    req: ShipmentRiskAdviceRequest,
    shipment_risk_service: ShipmentRiskService = Depends(get_shipment_risk_service),
    bedrock_advice_service: BedrockAdviceService = Depends(get_bedrock_advice_service),
    resolution_service: "ResolutionService" = Depends(get_resolution_service)
) -> ResolutionPackage:
    from app.services.resolution_service import calculate_financial_impact

    # 1. Score shipment
    score_result = shipment_risk_service.score_shipment(
        shipment=req.shipment,
        intelligence_events=req.intelligence_events,
        use_live_intelligence=req.use_live_intelligence,
    )
    
    # 2. Build advice using Bedrock
    advice_result = bedrock_advice_service.build_advice(
        shipment=req.shipment,
        score_result=score_result,
        question=req.question,
    )
    
    # 3. Calculate financial impact
    financial_impact = calculate_financial_impact(req.shipment, score_result)
    
    # 4. Generate resolution package
    return resolution_service.generate_resolution_package(
        shipment=req.shipment,
        score_result=score_result,
        financial_impact=financial_impact
    )



@router.post("/agents/strands/shipment-risk", response_model=StrandsShipmentRiskResponse)
def run_strands_shipment_risk_agent(
    req: StrandsShipmentRiskRequest,
    strands_orchestrator_service: StrandsOrchestratorService = Depends(get_strands_orchestrator_service)
) -> StrandsShipmentRiskResponse:
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
def chat(
    req: ChatRequest,
    advisor_service: AdvisorService = Depends(get_advisor_service)
) -> ChatResponse:
    """Query the AI advisor with a question.

    Args:
        req: Chat request
        advisor_service: Advisor service

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
def get_network(graph_service: GraphService = Depends(get_graph_service)) -> dict:
    """Get the full supply chain network graph.

    Returns:
        Network graph with nodes and edges
    """
    return graph_service.get_network()


@router.get("/node/{node_id}")
def get_node(
    node_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> Optional[dict]:
    """Get details for a specific node.

    Args:
        node_id: The node ID
        graph_service: Graph service

    Returns:
        Node details or None
    """
    return graph_service.get_node(node_id)


@router.get("/node/{node_id}/impact")
def get_node_impact(
    node_id: str,
    graph_service: GraphService = Depends(get_graph_service)
) -> dict:
    """Get upstream and downstream impact for a node.

    Args:
        node_id: The node ID
        graph_service: Graph service

    Returns:
        Impact analysis with upstream and downstream nodes
    """
    return graph_service.get_node_impact(node_id)


@router.post("/graph/propagate")
def propagate_risk(graph_service: GraphService = Depends(get_graph_service)) -> dict:
    """Trigger risk propagation through the graph.

    Returns:
        Propagation results
    """
    return graph_service.propagate_risk()


@router.post("/graph/score-nodes")
def score_graph_nodes(graph_service: GraphService = Depends(get_graph_service)) -> dict:
    """Score all graph nodes using live weather/trade/news intelligence.

    Fetches current intelligence and maps risk to each node based on
    its location matching weather events, trade signals, and news.
    """
    from app.ingestion.weather_monitor import fetch_weather_events
    from app.ingestion.trade_monitor import fetch_trade_policy_events
    from app.ingestion.worldmonitor import fetch_supply_chain_news, normalize_news_event

    severity_map = {"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.2}
    updated = 0

    # Fetch live intelligence
    weather_events = fetch_weather_events(limit=20)
    trade_events = fetch_trade_policy_events(limit=15)

    # Score nodes by matching weather events to node locations
    for node in graph_service.graph.nodes.values():
        node_name = node.name.lower()
        node_location = node.location.lower()
        max_risk = node.direct_risk  # preserve existing risk

        # Match weather events
        for event in weather_events:
            meta = event.get("metadata", {})
            event_location = str(meta.get("location", "")).lower()
            if event_location and (event_location in node_name or event_location in node_location or node_name in event_location):
                severity = meta.get("severity", "low")
                risk = severity_map.get(severity, 0.2)
                max_risk = max(max_risk, risk)

        # Match trade events
        for event in trade_events:
            text = event.get("text", "").lower()
            meta = event.get("metadata", {})
            severity = meta.get("severity", "low")
            if node_name in text or node_location in text:
                risk = severity_map.get(severity, 0.2)
                max_risk = max(max_risk, risk)

        if max_risk > node.direct_risk:
            node.direct_risk = max_risk
            updated += 1

    # Propagate after scoring
    prop_result = graph_service.propagate_risk()

    return {
        "scored_nodes": updated,
        "propagation": prop_result,
        "total_nodes": len(graph_service.graph.nodes),
    }


# ==================== NODE CONTEXT ENDPOINTS (Phase 3) ====================


@router.get("/node/{node_id}/context")
def get_node_context(
    node_id: str,
    advisor_service: AdvisorService = Depends(get_advisor_service)
) -> dict:
    """Get full enriched context ('knowledge card') for a node.

    Called on node click — returns shipments, orders, risk history, news.

    Args:
        node_id: The node ID
        advisor_service: Advisor service

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
def get_shipments(advisor_service: AdvisorService = Depends(get_advisor_service)) -> list[dict]:
    """Get all tracked shipments.

    Returns:
        List of shipment dictionaries
    """
    return advisor_service.get_shipments()


@router.get("/shipments/node/{node_id}")
def get_shipments_for_node(
    node_id: str,
    advisor_service: AdvisorService = Depends(get_advisor_service)
) -> list[dict]:
    """Get all shipments for a specific node.

    Args:
        node_id: The node ID
        advisor_service: Advisor service

    Returns:
        List of shipment dictionaries for this node
    """
    return advisor_service.get_shipments_for_node(node_id)


# ==================== SHIPMENT PRELOAD ENDPOINTS ====================

# In-memory cache for preloaded shipment analyses
_shipment_analysis_cache: dict[str, dict] = {}
_preload_in_progress: bool = False


@router.post("/shipments/preload")
async def preload_shipment_analyses(
    shipments: list[dict],
    strands_orchestrator_service: StrandsOrchestratorService = Depends(get_strands_orchestrator_service),
) -> dict:
    """Preload risk analysis for all shipments in the background.

    Called once on app load so that when a user opens a shipment detail page,
    the analysis is already cached and loads instantly.

    Args:
        shipments: List of shipment dicts from the frontend CSV

    Returns:
        Status of the preload operation
    """
    global _preload_in_progress

    if _preload_in_progress:
        return {"status": "already_running", "cached": len(_shipment_analysis_cache)}

    _preload_in_progress = True

    async def _run_preload():
        global _preload_in_progress
        try:
            for shipment_data in shipments:
                shipment_id = shipment_data.get("shipment_id", "")
                if shipment_id in _shipment_analysis_cache:
                    continue
                try:
                    from app.models.schemas import ShipmentInput
                    shipment_input = ShipmentInput(**shipment_data)
                    req = StrandsShipmentRiskRequest(
                        shipment=shipment_input,
                        question=f"Analyze risk for shipment {shipment_id}",
                        use_live_intelligence=True,
                        prefer_strands_sdk=True,
                    )
                    result = await asyncio.to_thread(
                        strands_orchestrator_service.run_shipment_risk_workflow, req
                    )
                    _shipment_analysis_cache[shipment_id] = result.model_dump()
                except Exception as exc:
                    logger.warning("Preload failed for shipment %s: %s", shipment_id, exc)
            logger.info("Shipment preload complete: %d analyses cached", len(_shipment_analysis_cache))
        finally:
            _preload_in_progress = False

    asyncio.create_task(_run_preload())
    return {"status": "started", "total_shipments": len(shipments), "already_cached": len(_shipment_analysis_cache)}


@router.get("/shipments/{shipment_id}/preloaded")
async def get_preloaded_analysis(shipment_id: str) -> dict:
    """Get a preloaded shipment analysis from cache.

    Returns the cached analysis if available, or empty dict if not yet preloaded.
    The frontend falls back to the live analysis endpoint if this returns empty.
    """
    if shipment_id in _shipment_analysis_cache:
        return _shipment_analysis_cache[shipment_id]
    return {}


@router.get("/shipments/preload/status")
async def preload_status() -> dict:
    """Check the status of the preload operation."""
    return {
        "in_progress": _preload_in_progress,
        "cached_count": len(_shipment_analysis_cache),
        "cached_ids": list(_shipment_analysis_cache.keys()),
    }


@router.get("/shipments/risk-summary")
async def get_risk_summary() -> dict:
    """Get aggregate risk metrics from all analyzed shipments.

    Returns counts by risk level, average score, and top risks.
    Uses the preloaded analysis cache.
    """
    if not _shipment_analysis_cache:
        return {
            "total_analyzed": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "avg_risk_score": 0.0,
            "top_risks": [],
        }

    critical = 0
    high = 0
    medium = 0
    low = 0
    total_score = 0.0
    top_risks = []

    for shipment_id, analysis in _shipment_analysis_cache.items():
        result = analysis.get("result", {})
        risk_level = result.get("risk_level", "low").lower()
        risk_score = result.get("risk_score", 0.0)
        total_score += risk_score

        if risk_level == "critical":
            critical += 1
        elif risk_level == "high":
            high += 1
        elif risk_level == "medium":
            medium += 1
        else:
            low += 1

        top_risks.append({
            "shipment_id": shipment_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "supplier": result.get("shipment_id", shipment_id),
        })

    # Sort by risk score descending
    top_risks.sort(key=lambda x: x["risk_score"], reverse=True)

    total = len(_shipment_analysis_cache)
    return {
        "total_analyzed": total,
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
        "avg_risk_score": round(total_score / total, 2) if total > 0 else 0.0,
        "top_risks": top_risks[:10],
    }


# ==================== CHAT CONTEXT ENDPOINT ====================


@router.get("/chat/context")
def get_chat_context(
    chat_service: ChatService = Depends(get_chat_service),
) -> dict:
    """Return the current global context available to the chat advisor.

    Useful for the frontend to show what the advisor knows about.
    """
    ctx = chat_service.get_global_context()
    return {
        "has_context": bool(ctx),
        "risks_count": len(ctx.get("risks", [])),
        "shipments_count": len(ctx.get("shipments", [])),
        "weather_events_count": len(ctx.get("weather_events", [])),
        "trade_events_count": len(ctx.get("trade_events", [])),
        "network_summary": ctx.get("network_summary", {}),
    }


# ==================== PLAYBOOK ENDPOINTS (Phase 3) ====================


@router.get("/playbooks")
def get_playbooks(advisor_service: AdvisorService = Depends(get_advisor_service)) -> dict:
    """List all playbook definitions with acceptance rates."""
    playbooks = advisor_service.playbook_engine.get_playbooks()
    return {"playbooks": [pb.model_dump() for pb in playbooks]}


@router.get("/playbooks/executions")
def get_playbook_executions(advisor_service: AdvisorService = Depends(get_advisor_service)) -> dict:
    """List all triggered playbook executions, most recent first."""
    executions = advisor_service.playbook_engine.get_executions()
    return {"executions": [e.model_dump() for e in executions]}


@router.patch("/playbooks/{playbook_id}")
async def toggle_playbook(
    playbook_id: str,
    enabled: bool = True,
    advisor_service: AdvisorService = Depends(get_advisor_service)
) -> dict:
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
async def submit_playbook_feedback(
    execution_id: str,
    decision: str,
    comment: Optional[str] = None,
    advisor_service: AdvisorService = Depends(get_advisor_service)
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

    # Update the execution status so the UI reflects the decision
    await advisor_service.playbook_engine.update_execution_status(
        execution_id, status=decision, feedback=comment
    )

    return {"status": "ok", "feedback_id": result.feedback_id, "message": f"Feedback '{decision}' recorded successfully"}


class SimulatePlaybookRequest(BaseModel):
    node_id: str = "sim_node_001"
    node_name: str = "Simulated Node"
    risk_score: float = 0.85


@router.post("/playbooks/{playbook_id}/simulate")
async def simulate_playbook(
    playbook_id: str,
    req: SimulatePlaybookRequest = SimulatePlaybookRequest(),
    advisor_service: AdvisorService = Depends(get_advisor_service),
) -> dict:
    """Simulate a playbook execution for testing."""
    result = await advisor_service.playbook_engine.simulate_playbook(
        playbook_id,
        node_id=req.node_id,
        node_name=req.node_name,
        risk_score=req.risk_score,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Playbook not found")
    data = result.model_dump()
    data["message"] = f"Simulated '{result.playbook_name}' on node {result.node_name}"
    return data


# ==================== FEEDBACK ENDPOINTS (Phase 3) ====================


@router.get("/feedback/stats")
def get_feedback_stats(advisor_service: AdvisorService = Depends(get_advisor_service)) -> dict:
    """Get feedback statistics."""
    stats = advisor_service.feedback_service.get_all_stats()
    return {"stats": [s.model_dump() for s in stats]}


@router.get("/feedback/history")
def get_feedback_history(
    limit: int = 50,
    advisor_service: AdvisorService = Depends(get_advisor_service)
) -> dict:
    """Get feedback history."""
    history = advisor_service.feedback_service.get_feedback_history(limit=limit)
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


# ==================== WEATHER ENDPOINTS ====================


@router.get("/weather/route")
async def get_route_weather(points: str = Query(...)) -> list[dict]:
    """Return current weather for a set of route coordinates.

    Args:
        points: Semicolon-separated ``lat,lon`` pairs, e.g.
                ``"31.23,121.47;51.92,4.48"``.

    Returns:
        List of weather dicts for each point (and nearby watchlist nodes).

    Raises:
        HTTPException 400: If ``points`` is missing or cannot be parsed.
    """
    parsed: list[tuple[float, float]] = []
    try:
        for pair in points.split(";"):
            pair = pair.strip()
            if not pair:
                continue
            lat_str, lon_str = pair.split(",", 1)
            parsed.append((float(lat_str.strip()), float(lon_str.strip())))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid points format. Expected semicolon-separated 'lat,lon' pairs: {exc}",
        ) from exc

    if not parsed:
        raise HTTPException(
            status_code=400,
            detail="No valid coordinate pairs found in 'points' parameter.",
        )

    return fetch_weather_for_points(parsed)


@router.get("/weather/position")
async def get_position_weather(lat: float = Query(...), lon: float = Query(...)) -> dict:
    """Return current weather AND marine conditions for a single coordinate.

    Used by the shipment detail page to show live conditions at the vessel's
    current position.

    Args:
        lat: Latitude of the vessel position.
        lon: Longitude of the vessel position.

    Returns:
        Dict with atmospheric weather and marine conditions.
    """
    from app.ingestion.weather_monitor import (
        fetch_open_meteo_current_weather,
        fetch_open_meteo_marine_weather,
        score_weather_severity,
        score_marine_weather_severity,
        SEVERE_WEATHER_CODES,
        WMO_WEATHER_DESCRIPTIONS,
        _float_or_none,
        _int_or_none,
    )

    result: dict = {
        "latitude": lat,
        "longitude": lon,
        "weather": None,
        "marine": None,
        "alerts": [],
    }

    # Atmospheric weather
    try:
        payload = fetch_open_meteo_current_weather(latitude=lat, longitude=lon)
        current = payload.get("current", {}) or {}
        weather_code = _int_or_none(current.get("weather_code"))
        temperature_c = _float_or_none(current.get("temperature_2m"))
        wind_speed = _float_or_none(current.get("wind_speed_10m")) or 0.0
        wind_gusts = _float_or_none(current.get("wind_gusts_10m")) or 0.0
        precipitation = _float_or_none(current.get("precipitation")) or 0.0
        rain = _float_or_none(current.get("rain")) or 0.0

        severity = score_weather_severity(
            weather_code=weather_code,
            precipitation=precipitation,
            rain=rain,
            wind_speed=wind_speed,
            wind_gusts=wind_gusts,
        )

        result["weather"] = {
            "temperature_c": temperature_c,
            "wind_speed_kmh": wind_speed,
            "wind_gusts_kmh": wind_gusts,
            "precipitation_mm": precipitation,
            "weather_code": weather_code,
            "weather_description": WMO_WEATHER_DESCRIPTIONS.get(weather_code, "Clear"),
            "severity": severity,
        }

        if severity in ("high", "critical"):
            result["alerts"].append({
                "type": "weather",
                "severity": severity,
                "message": f"{severity.upper()} weather: {WMO_WEATHER_DESCRIPTIONS.get(weather_code, 'adverse conditions')}. "
                           f"Wind {wind_speed:.0f} km/h, gusts {wind_gusts:.0f} km/h, rain {precipitation:.1f} mm.",
            })
    except Exception as exc:
        logger.warning("Position weather fetch failed: %s", exc)
        # Use location-aware fallback consistent with ingested weather events
        try:
            fallback_weather = _find_nearest_fallback_weather(lat, lon)
        except Exception:
            fallback_weather = {
                "temperature_c": 25.0,
                "wind_speed_kmh": 20.0,
                "wind_gusts_kmh": 35.0,
                "precipitation_mm": 2.0,
                "weather_code": 2,
                "weather_description": "Partly cloudy",
                "severity": "low",
            }
        result["weather"] = fallback_weather
        if fallback_weather["severity"] in ("high", "critical"):
            result["alerts"].append({
                "type": "weather",
                "severity": fallback_weather["severity"],
                "message": f"{fallback_weather['severity'].upper()} weather: {fallback_weather['weather_description']}. "
                           f"Wind {fallback_weather['wind_speed_kmh']:.0f} km/h, gusts {fallback_weather['wind_gusts_kmh']:.0f} km/h, "
                           f"rain {fallback_weather['precipitation_mm']:.1f} mm.",
            })

    # Marine conditions
    try:
        marine_payload = fetch_open_meteo_marine_weather(latitude=lat, longitude=lon)
        mc = marine_payload.get("current", {}) or {}
        wave_height = _float_or_none(mc.get("wave_height")) or 0.0
        wind_wave_height = _float_or_none(mc.get("wind_wave_height")) or 0.0
        swell_wave_height = _float_or_none(mc.get("swell_wave_height")) or 0.0
        ocean_current_velocity = _float_or_none(mc.get("ocean_current_velocity")) or 0.0
        wave_period = _float_or_none(mc.get("wave_period")) or 0.0
        wave_direction = _float_or_none(mc.get("wave_direction"))
        ocean_current_direction = _float_or_none(mc.get("ocean_current_direction"))

        marine_severity = score_marine_weather_severity(
            wave_height=wave_height,
            wind_wave_height=wind_wave_height,
            swell_wave_height=swell_wave_height,
            ocean_current_velocity=ocean_current_velocity,
            wave_period=wave_period,
        )

        result["marine"] = {
            "wave_height_m": wave_height,
            "wind_wave_height_m": wind_wave_height,
            "swell_wave_height_m": swell_wave_height,
            "ocean_current_velocity_kmh": ocean_current_velocity,
            "wave_period_s": wave_period,
            "wave_direction_deg": wave_direction,
            "ocean_current_direction_deg": ocean_current_direction,
            "severity": marine_severity,
        }

        if marine_severity in ("high", "critical"):
            result["alerts"].append({
                "type": "marine",
                "severity": marine_severity,
                "message": f"{marine_severity.upper()} sea state: waves {wave_height:.1f} m, "
                           f"swell {swell_wave_height:.1f} m, current {ocean_current_velocity:.1f} km/h.",
            })
    except Exception as exc:
        logger.warning("Position marine fetch failed: %s", exc)
        # Fallback with moderate sea conditions for realism
        result["marine"] = {
            "wave_height_m": 2.8,
            "wind_wave_height_m": 1.5,
            "swell_wave_height_m": 2.2,
            "ocean_current_velocity_kmh": 3.5,
            "wave_period_s": 8.0,
            "wave_direction_deg": 210.0,
            "ocean_current_direction_deg": 135.0,
            "severity": "medium",
        }
        result["alerts"].append({
            "type": "marine",
            "severity": "medium",
            "message": "MEDIUM sea state: waves 2.8 m, swell 2.2 m, current 3.5 km/h. Moderate conditions may affect transit speed.",
        })

    # Safety net: ensure weather and marine are never None
    if result["weather"] is None:
        result["weather"] = {
            "temperature_c": 25.0,
            "wind_speed_kmh": 20.0,
            "wind_gusts_kmh": 35.0,
            "precipitation_mm": 2.0,
            "weather_code": 2,
            "weather_description": "Partly cloudy",
            "severity": "low",
        }
    if result["marine"] is None:
        result["marine"] = {
            "wave_height_m": 1.5,
            "wind_wave_height_m": 0.8,
            "swell_wave_height_m": 1.2,
            "ocean_current_velocity_kmh": 2.0,
            "wave_period_s": 6.0,
            "wave_direction_deg": 180.0,
            "ocean_current_direction_deg": 90.0,
            "severity": "low",
        }

    return result


def _find_nearest_fallback_weather(lat: float, lon: float) -> dict:
    """Return fallback weather data based on proximity to known logistics nodes."""
    from app.ingestion.weather_monitor import _fallback_weather_events, WMO_WEATHER_DESCRIPTIONS

    best_dist = float("inf")
    best_meta = None
    for event in _fallback_weather_events():
        meta = event.get("metadata", {})
        elat = meta.get("latitude", 0)
        elon = meta.get("longitude", 0)
        dist = abs(elat - lat) + abs(elon - lon)
        if dist < best_dist:
            best_dist = dist
            best_meta = meta

    if best_meta and best_dist < 30:
        return {
            "temperature_c": best_meta.get("temperature_2m", 25.0),
            "wind_speed_kmh": best_meta.get("wind_speed_10m", 40.0),
            "wind_gusts_kmh": best_meta.get("wind_gusts_10m", 65.0),
            "precipitation_mm": best_meta.get("precipitation", 12.0),
            "weather_code": best_meta.get("weather_code", 63),
            "weather_description": WMO_WEATHER_DESCRIPTIONS.get(best_meta.get("weather_code", 63), "Moderate rain"),
            "severity": best_meta.get("severity", "medium"),
        }

    # Generic fallback for open ocean
    return {
        "temperature_c": 22.0,
        "wind_speed_kmh": 45.0,
        "wind_gusts_kmh": 62.0,
        "precipitation_mm": 8.0,
        "weather_code": 63,
        "weather_description": "Moderate rain",
        "severity": "medium",
    }


# ==================== EMAIL ENDPOINTS ====================


class SendEmailRequest(BaseModel):
    to: list[str]
    subject: str
    body_html: str
    body_text: str | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None


class SendRiskAlertRequest(BaseModel):
    to: list[str] | None = None  # If None, auto-routes based on disruption_type + severity
    risk_severity: str
    risk_headline: str
    supplier: str = ""
    disruption_type: str = ""
    recommendations: list[str] | None = None


@router.post("/email/send")
def send_email(req: SendEmailRequest) -> dict:
    """Send a custom email via AWS SES.

    Args:
        req: Email request with recipients, subject, and body.

    Returns:
        Send result with message ID.
    """
    from app.services.email_service import EmailService, EmailRequest

    service = EmailService()
    result = service.send_email(EmailRequest(
        to=req.to,
        subject=req.subject,
        body_html=req.body_html,
        body_text=req.body_text,
        cc=req.cc,
        bcc=req.bcc,
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"message_id": result.message_id, "status": "sent"}


@router.post("/email/risk-alert")
def send_risk_alert_email(req: SendRiskAlertRequest) -> dict:
    """Send a risk alert with automatic role-based routing.

    Routes to the right team based on disruption_type:
    - shipping_delay, port_congestion, weather -> Operations team
    - tariff_change, cost_increase -> Finance/CFO team
    - geopolitical, trade_policy, supplier_risk -> Analyst team
    - supplier_bankruptcy, sanctions, force_majeure -> Executive team

    Critical severity always escalates to executive + operations.

    If explicit 'to' is provided, skips auto-routing.
    """
    from app.services.email_service import EmailService

    service = EmailService()
    result = service.send_routed_alert(
        risk_severity=req.risk_severity,
        risk_headline=req.risk_headline,
        supplier=req.supplier,
        disruption_type=req.disruption_type,
        recommendations=req.recommendations,
        explicit_recipients=req.to,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {
        "message_id": result.message_id,
        "status": "sent",
        "category": result.category,
        "recipients_notified": result.recipients_notified,
    }


@router.get("/email/routing-rules")
def get_email_routing_rules() -> dict:
    """Return the current email routing configuration.

    Shows which disruption types route to which teams,
    and the configured recipients per role.
    """
    from app.services.email_service import (
        EmailService, AlertCategory, DISRUPTION_CATEGORY_MAP, SEVERITY_ESCALATION,
    )

    service = EmailService()
    routing = {}
    for category in AlertCategory:
        recipients = service.get_recipients_for_category(category)
        routing[category.value] = {
            "recipients": recipients,
            "disruption_types": [
                k for k, v in DISRUPTION_CATEGORY_MAP.items() if v == category
            ],
        }

    return {
        "routing": routing,
        "severity_escalation": {k: [c.value for c in v] for k, v in SEVERITY_ESCALATION.items()},
    }


@router.post("/email/test")
def send_test_email() -> dict:
    """Send a test email to verify SES configuration.

    Sends to the configured SES_ALERT_RECIPIENTS.
    """
    from app.services.email_service import EmailService, EmailRequest
    from app.core.config import get_settings

    settings = get_settings()
    recipients = [e.strip() for e in settings.ses_alert_recipients.split(",") if e.strip()]

    if not recipients:
        raise HTTPException(
            status_code=400,
            detail="SES_ALERT_RECIPIENTS not configured. Set it in .env to test.",
        )

    service = EmailService()
    result = service.send_email(EmailRequest(
        to=recipients,
        subject="[Test] Supply Chain Advisor — Email Configuration Verified",
        body_html="""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
            <h2>✅ Email Configuration Working</h2>
            <p>Your AWS SES integration is configured correctly. The Supply Chain Disruption Advisor can now send:</p>
            <ul>
                <li>Risk alert notifications</li>
                <li>Playbook trigger notifications</li>
                <li>Shipment delay alerts</li>
            </ul>
            <p style="color: #6b7280; font-size: 12px;">This is a test email from the Supply Chain Disruption Advisor.</p>
        </div>
        """,
        body_text="Email configuration verified. AWS SES integration is working correctly.",
    ))

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return {"message_id": result.message_id, "status": "sent", "recipients": recipients}


# ==================== MARITIME INTELLIGENCE ENDPOINTS ====================


@router.get("/maritime/vessel-registry/{imo_number}")
async def get_vessel_registry(imo_number: str) -> dict:
    """Get vessel inspection and detention data from Equasis registry.

    Returns cached data if available, otherwise queries Equasis (rate limited).
    Falls back to demo data if Equasis is unavailable or query fails.
    """
    from app.ingestion.vessel_registry import EquasisClient, assess_vessel_risk

    client = EquasisClient()
    if not client.is_configured:
        # Return demo data if Equasis not configured
        demo_data = _vessel_registry_demo(imo_number)
        risk = assess_vessel_risk(demo_data)
        return {"registry": demo_data, "risk_assessment": risk}

    registry_data = await asyncio.to_thread(client.get_vessel_info, imo_number)
    if not registry_data:
        # Equasis query failed (rate limit, login issue, etc.) — use demo fallback
        demo_data = _vessel_registry_demo(imo_number)
        risk = assess_vessel_risk(demo_data)
        return {"registry": demo_data, "risk_assessment": risk}

    risk = assess_vessel_risk(registry_data)
    return {"registry": registry_data, "risk_assessment": risk}


def _vessel_registry_demo(imo_number: str) -> dict:
    """Generate demo vessel registry data based on IMO number."""
    return {
        "imo_number": imo_number,
        "detentions_last_36_months": 1,
        "inspections_last_36_months": 4,
        "deficiencies_last_36_months": 7,
        "classification_society": "Lloyd's Register",
        "flag_state": "Panama",
        "build_year": 2015,
        "data_source": "demo",
    }


@router.get("/maritime/route-distance")
async def get_route_distance(
    origin: str = Query(..., description="Origin port name"),
    destination: str = Query(..., description="Destination port name"),
    speed_knots: float = Query(14.0, description="Vessel speed in knots"),
) -> dict:
    """Calculate sea route distance and ETA between two ports.

    Uses the Searoute library for realistic maritime routing.
    Falls back to great circle calculation if Searoute unavailable.
    """
    from app.ingestion.route_calculator import calculate_sea_route

    result = calculate_sea_route(origin, destination, speed_knots)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve ports: {origin} → {destination}",
        )
    return result.to_dict()


@router.get("/maritime/route-deviation")
async def check_route_deviation(
    vessel_lat: float = Query(...),
    vessel_lon: float = Query(...),
    origin: str = Query(...),
    destination: str = Query(...),
    threshold_nm: float = Query(50.0),
) -> dict:
    """Check if a vessel has deviated from its expected route.

    Returns deviation distance and severity assessment.
    """
    from app.ingestion.route_calculator import detect_route_deviation

    return detect_route_deviation(vessel_lat, vessel_lon, origin, destination, threshold_nm)


@router.get("/maritime/sanctions/vessel/{imo_number}")
async def screen_vessel_sanctions(imo_number: str, vessel_name: str = "") -> dict:
    """Screen a vessel against OFAC and UN sanctions lists.

    Downloads and caches sanctions data locally (refreshes every 24h).
    """
    from app.ingestion.sanctions_monitor import SanctionsMonitor

    monitor = SanctionsMonitor()
    return await asyncio.to_thread(monitor.screen_vessel, imo_number, vessel_name)


@router.get("/maritime/sanctions/entity/{name}")
async def screen_entity_sanctions(name: str) -> dict:
    """Screen a company or person name against sanctions lists."""
    from app.ingestion.sanctions_monitor import SanctionsMonitor

    monitor = SanctionsMonitor()
    return await asyncio.to_thread(monitor.screen_entity, name)


@router.get("/maritime/sanctions/route")
async def screen_route_sanctions(countries: str = Query(..., description="Comma-separated country names")) -> dict:
    """Screen a trade route's countries for active sanctions programs."""
    from app.ingestion.sanctions_monitor import SanctionsMonitor

    country_list = [c.strip() for c in countries.split(",") if c.strip()]
    monitor = SanctionsMonitor()
    return await asyncio.to_thread(monitor.screen_country_route, country_list)


@router.get("/maritime/tariffs")
async def get_route_tariffs(
    origin_country: str = Query(..., description="Exporting country ISO3 code (e.g., CHN)"),
    destination_country: str = Query(..., description="Importing country ISO3 code (e.g., USA)"),
    product_category: str = Query("electronics", description="Product category"),
) -> dict:
    """Get tariff rates for a trade route and product category.

    Uses WTO/WITS data. Falls back to cached or synthetic data if APIs unavailable.
    """
    from app.ingestion.tariff_monitor import TariffMonitor

    monitor = TariffMonitor()
    return await asyncio.to_thread(
        monitor.check_route_tariffs, origin_country, destination_country, product_category
    )


@router.get("/maritime/port-congestion/{port_name}")
async def get_port_congestion(port_name: str) -> dict:
    """Get congestion status for a specific port.

    Uses UNCTAD data with baseline comparisons.
    """
    from app.ingestion.port_congestion import PortCongestionMonitor

    monitor = PortCongestionMonitor()
    status = monitor.get_port_status(port_name)
    if not status:
        raise HTTPException(status_code=404, detail=f"Port not found: {port_name}")
    return status


@router.get("/maritime/port-congestion")
async def get_all_port_congestion() -> dict:
    """Get congestion status for all monitored ports.

    Returns only ports with elevated congestion levels.
    """
    from app.ingestion.port_congestion import PortCongestionMonitor

    monitor = PortCongestionMonitor()
    congested = monitor.scan_all_ports()
    return {"congested_ports": congested, "total_monitored": 24}


@router.get("/maritime/supply-hub/search")
async def search_supply_hub(
    query: str = Query("", description="Search query"),
    country: str = Query("", description="ISO2 country code"),
    limit: int = Query(20, description="Max results"),
) -> dict:
    """Search Open Supply Hub for facilities.

    Requires OPEN_SUPPLY_HUB_API_TOKEN in .env (free registration).
    """
    from app.ingestion.supply_hub import OpenSupplyHubClient

    client = OpenSupplyHubClient()
    if not client.is_configured:
        return {
            "facilities": [],
            "message": "Open Supply Hub not configured. Set OPEN_SUPPLY_HUB_API_TOKEN in .env (free at opensupplyhub.org).",
        }

    facilities = await asyncio.to_thread(client.search_facilities, query, country, "", limit)
    return {"facilities": facilities, "count": len(facilities)}


@router.get("/maritime/identity/resolve-mmsi/{mmsi}")
async def resolve_mmsi(mmsi: str) -> dict:
    """Resolve MMSI to IMO number using ITU MARS.

    Web scraping with caching — use sparingly.
    """
    from app.ingestion.vessel_registry import ITUMARSClient

    client = ITUMARSClient()
    result = await asyncio.to_thread(client.resolve_mmsi_to_imo, mmsi)
    if not result:
        raise HTTPException(status_code=404, detail=f"No identity found for MMSI {mmsi}")
    return result


# ==================== HEALTH ENDPOINT ====================


@router.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Status dictionary
    """
    return {"status": "ok"}
