from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_ai_client, get_current_workspace
from app.core.config import Settings, get_settings
from app.db.models import Workspace
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
    workspace: Workspace = Depends(get_current_workspace),
):
    embedding = ai_client.embed_texts([q]).embeddings[0]
    results = semantic_search(
        db,
        query_embedding=embedding,
        embedding_model=settings.openai_embedding_model,
        limit=limit,
        workspace_id=workspace.id,
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
def search_page(request: Request, workspace: Workspace = Depends(get_current_workspace)):
    return templates.TemplateResponse(request, "search.html", {"workspace": workspace})


def _wants_html(request: Request) -> bool:
    return request.headers.get("hx-request") == "true" or "text/html" in request.headers.get(
        "accept", ""
    )
