from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace
from app.core.config import Settings, get_settings
from app.db.models import Document, Post, Workspace
from app.db.session import SessionLocal, get_db
from app.main_templates import templates
from app.schemas.documents import DocumentRead
from app.services.public_ingestion import process_document_background, queue_upload, queue_url

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    post_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    workspace: Workspace = Depends(get_current_workspace),
) -> Document:
    post = db.get(Post, post_id) if post_id else None
    if post_id and post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    try:
        document = await queue_upload(
            db=db,
            settings=settings,
            file=file,
            workspace=workspace,
            post=post,
        )
        db.commit()
        db.refresh(document)
        _schedule_document_processing(request, background_tasks, document.id)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if request.headers.get("hx-request") == "true":
        return templates.TemplateResponse(
            request,
            "partials/source_added.html",
            {"document": document, "source_kind": "file"},
            status_code=status.HTTP_201_CREATED,
            background=background_tasks,
        )
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER, background=background_tasks)
    return document


@router.post("/url", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def add_url_document(
    request: Request,
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    post_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
) -> Document:
    post = db.get(Post, post_id) if post_id else None
    if post_id and post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    try:
        document = queue_url(
            db=db,
            url=url,
            workspace=workspace,
            post=post,
        )
        db.commit()
        db.refresh(document)
        _schedule_document_processing(request, background_tasks, document.id)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if request.headers.get("hx-request") == "true":
        return templates.TemplateResponse(
            request,
            "partials/source_added.html",
            {"document": document, "source_kind": "website"},
            status_code=status.HTTP_201_CREATED,
            background=background_tasks,
        )
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER, background=background_tasks)
    return document


@router.get("/status")
def document_status(
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
        "partials/document_list.html",
        {"documents": documents},
    )


def _schedule_document_processing(
    request: Request,
    background_tasks: BackgroundTasks,
    document_id: int,
) -> None:
    session_factory = getattr(request.app.state, "db_session_factory", SessionLocal)
    background_tasks.add_task(process_document_background, document_id, session_factory)
