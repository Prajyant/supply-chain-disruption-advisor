from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse, IngestRequest, IngestResponse, RiskAssessment
from app.services.advisor_service import AdvisorService

router = APIRouter()
service = AdvisorService()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> IngestResponse:
    try:
        return service.ingest(
            supplier_emails_path=req.supplier_emails_path,
            news_feed_path=req.news_feed_path,
            inventory_path=req.inventory_path,
            use_realtime_news=req.use_realtime_news,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to ingest data: {exc}") from exc


@router.get("/risks", response_model=list[RiskAssessment])
def risks() -> list[RiskAssessment]:
    return service.get_risks()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    return service.chat(question=req.question, top_k=req.top_k)
