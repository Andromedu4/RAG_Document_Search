from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_ai_client
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main_templates import templates
from app.schemas.search import SearchItem, SearchResponse
from app.services.ai_logging import LoggedAIClient
from app.services.search import semantic_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/semantic", response_model=SearchResponse)
def semantic_search_endpoint(
    request: Request,
    q: str = Query(min_length=2),
    limit: int = Query(default=8, ge=1, le=25),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: LoggedAIClient = Depends(get_ai_client),
):
    embedding = ai_client.embed_texts([q]).embeddings[0]
    results = semantic_search(
        db,
        query_embedding=embedding,
        embedding_model=settings.openai_embedding_model,
        limit=limit,
    )
    db.commit()
    items = [SearchItem(**result.__dict__) for result in results]
    if _wants_html(request):
        return templates.TemplateResponse(
            request,
            "partials/search_results.html",
            {"query": q, "results": items},
        )
    return SearchResponse(query=q, results=items)


@router.get("", response_class=HTMLResponse)
def search_page(request: Request):
    return templates.TemplateResponse(request, "search.html")


def _wants_html(request: Request) -> bool:
    return request.headers.get("hx-request") == "true" or "text/html" in request.headers.get(
        "accept", ""
    )
