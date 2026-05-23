from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_ai_client, get_current_workspace
from app.core.config import Settings, get_settings
from app.db.models import Document, PostChunk, Workspace
from app.db.session import get_db
from app.main_templates import templates
from app.schemas.rag import RagAskResponse, RelevantDocument
from app.services.ai_logging import LoggedAIClient
from app.services.rag import answer_question

router = APIRouter(prefix="/rag", tags=["rag"])
ACTIVE_DOCUMENT_STATUSES = {"queued", "fetching", "extracting", "indexing"}


@router.post("/ask", response_model=RagAskResponse)
async def ask_question(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: LoggedAIClient = Depends(get_ai_client),
    workspace: Workspace = Depends(get_current_workspace),
):
    question = await _read_question(request)
    pending_documents = db.scalar(
        select(func.count())
        .select_from(Document)
        .where(
            Document.workspace_id == workspace.id,
            Document.processing_status.in_(ACTIVE_DOCUMENT_STATUSES),
        )
    )
    ready_chunks = db.scalar(
        select(func.count()).select_from(PostChunk).where(PostChunk.workspace_id == workspace.id)
    )
    if pending_documents and not ready_chunks:
        response = RagAskResponse(
            question=question,
            answer="Документ еще индексируется. Подожди несколько секунд и задай вопрос снова.",
            citations=[],
            retrieved_chunk_ids=[],
            rag_run_id=0,
            relevant_documents=[],
            pipeline=["indexing", "question"],
        )
        if request.headers.get("hx-request") == "true" or "text/html" in request.headers.get("accept", ""):
            return templates.TemplateResponse(
                request,
                "partials/rag_answer.html",
                {
                    "result": response,
                    "displayed_sources": [],
                },
            )
        return response

    try:
        embedding = ai_client.embed_texts([question]).embeddings[0]
        result = answer_question(
            db,
            question=question,
            query_embedding=embedding,
            settings=settings,
            ai_client=ai_client,
            workspace_id=workspace.id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI request failed: {exc}",
        ) from exc
    response = RagAskResponse(
        question=question,
        answer=result.answer,
        citations=result.citations,
        retrieved_chunk_ids=[item.chunk_id for item in result.retrieved],
        rag_run_id=result.rag_run_id,
        relevant_documents=[RelevantDocument(**item.__dict__) for item in result.retrieved],
        pipeline=[
            "indexing",
            "question",
            "retrieval",
            "generation",
            "answer",
        ],
    )
    cited_chunk_ids = [citation["chunk_id"] for citation in result.citations]
    displayed_sources = [item for item in response.relevant_documents if item.chunk_id in cited_chunk_ids]
    if not displayed_sources and response.relevant_documents:
        displayed_sources = response.relevant_documents[:1]
    if request.headers.get("hx-request") == "true" or "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            request,
            "partials/rag_answer.html",
            {
                "result": response,
                "displayed_sources": displayed_sources,
            },
        )
    return response


@router.get("", response_class=HTMLResponse)
def rag_page(
    request: Request,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    documents = db.scalars(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.workspace_id == workspace.id)
        .order_by(Document.created_at.desc())
        .limit(12)
    ).all()
    return templates.TemplateResponse(
        request,
        "rag_document_search.html",
        {"documents": documents, "workspace": workspace},
    )


async def _read_question(request: Request) -> str:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        question = payload.get("question", "")
    else:
        form = await request.form()
        question = str(form.get("question", ""))
    question = question.strip()
    if len(question) < 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question is required")
    return question
