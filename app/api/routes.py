"""API routes for the supply chain disruption advisor."""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    IngestRequest,
    IngestResponse,
    RiskAssessment,
    LoginRequest,
    LoginResponse,
    User,
)
from app.services.advisor_service import AdvisorService
from app.services.graph_service import GraphService
from app.auth.jwt_handler import JWTHandler
from app.auth.rbac import authenticate_user, Role, require_permission
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()
advisor_service = AdvisorService()
graph_service = GraphService()

# Load sample graph
graph_service.load_sample_graph()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get the current user from JWT token.

    Args:
        credentials: The HTTP authorization credentials

    Returns:
        User dictionary

    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    payload = JWTHandler.verify_token(token, "access")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    from app.auth.rbac import get_user
    user = get_user(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_user_role(user: dict = Depends(get_current_user)) -> Role:
    """Get the current user's role.

    Args:
        user: The user dictionary

    Returns:
        The user's role
    """
    return user.get("role", Role.VIEWER)


# ==================== AUTHENTICATION ENDPOINTS ====================


@router.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest) -> LoginResponse:
    """Authenticate a user and return tokens.

    Args:
        req: Login request with username and password

    Returns:
        Login response with tokens and user info
    """
    user = authenticate_user(req.username, req.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = JWTHandler.create_access_token({"sub": user["username"]})
    refresh_token = JWTHandler.create_refresh_token({"sub": user["username"]})

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=User(
            id=user["id"],
            username=user["username"],
            role=user["role"].value,
        ),
    )


@router.post("/auth/refresh")
def refresh_token(refresh_token: str) -> dict[str, str]:
    """Refresh an access token using a refresh token.

    Args:
        refresh_token: The refresh token

    Returns:
        Dictionary with new access token
    """
    payload = JWTHandler.verify_token(refresh_token, "refresh")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    access_token = JWTHandler.create_access_token({"sub": username})

    return {"access_token": access_token}


# ==================== INGESTION ENDPOINTS ====================


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    req: IngestRequest,
    user: dict = Depends(get_current_user),
    user_role: Role = Depends(get_user_role),
) -> IngestResponse:
    """Ingest data from multiple sources.

    Args:
        req: Ingestion request
        user: Current user
        user_role: User's role

    Returns:
        Ingestion response with statistics

    Raises:
        HTTPException: If user lacks permission
    """
    if not require_permission("ingest"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

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
def risks(user: dict = Depends(get_current_user)) -> list[RiskAssessment]:
    """Get all risk assessments.

    Args:
        user: Current user

    Returns:
        List of risk assessments
    """
    return advisor_service.get_risks()


@router.get("/risks/{risk_id}", response_model=RiskAssessment)
def get_risk(risk_id: str, user: dict = Depends(get_current_user)) -> RiskAssessment:
    """Get a specific risk by ID.

    Args:
        risk_id: The risk ID
        user: Current user

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


# ==================== CHAT ENDPOINTS ====================


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(get_current_user)) -> ChatResponse:
    """Query the AI advisor with a question.

    Args:
        req: Chat request
        user: Current user

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
def get_network(user: dict = Depends(get_current_user)) -> dict:
    """Get the full supply chain network graph.

    Args:
        user: Current user

    Returns:
        Network graph with nodes and edges
    """
    return graph_service.get_network()


@router.get("/node/{node_id}")
def get_node(node_id: str, user: dict = Depends(get_current_user)) -> Optional[dict]:
    """Get details for a specific node.

    Args:
        node_id: The node ID
        user: Current user

    Returns:
        Node details or None
    """
    return graph_service.get_node(node_id)


@router.get("/node/{node_id}/impact")
def get_node_impact(node_id: str, user: dict = Depends(get_current_user)) -> dict:
    """Get upstream and downstream impact for a node.

    Args:
        node_id: The node ID
        user: Current user

    Returns:
        Impact analysis with upstream and downstream nodes
    """
    return graph_service.get_node_impact(node_id)


@router.post("/graph/propagate")
def propagate_risk(user: dict = Depends(get_current_user)) -> dict:
    """Trigger risk propagation through the graph.

    Args:
        user: Current user

    Returns:
        Propagation results
    """
    return graph_service.propagate_risk()


# ==================== NODE CONTEXT ENDPOINTS ====================


@router.get("/node/{node_id}/context")
def get_node_context(node_id: str, user: dict = Depends(get_current_user)) -> dict:
    """Get full enriched context ('knowledge card') for a node.

    Called on node click — returns shipments, orders, risk history, news.

    Args:
        node_id: The node ID
        user: Current user

    Returns:
        Full NodeContext dictionary

    Raises:
        HTTPException: If node not found
    """
    context = advisor_service.get_node_context(node_id)
    if not context:
        raise HTTPException(status_code=404, detail="Node not found")
    return context


# ==================== SHIPMENT ENDPOINTS ====================


@router.get("/shipments")
def get_shipments(user: dict = Depends(get_current_user)) -> list[dict]:
    """Get all tracked shipments.

    🔴 CRITICAL FIX #3: This route was referenced in api.ts but
    was missing from the backend — would 404 on Dashboard load.

    Args:
        user: Current user

    Returns:
        List of shipment dictionaries
    """
    return advisor_service.get_shipments()


@router.get("/shipments/node/{node_id}")
def get_shipments_for_node(
    node_id: str, user: dict = Depends(get_current_user)
) -> list[dict]:
    """Get all shipments for a specific node.

    Args:
        node_id: The node ID
        user: Current user

    Returns:
        List of shipment dictionaries for this node
    """
    return advisor_service.get_shipments_for_node(node_id)


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
