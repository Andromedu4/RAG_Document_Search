from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_ai_client, get_current_workspace
from app.core.config import Settings, get_settings
from app.db.models import Document, Post, Workspace
from app.db.session import get_db
from app.main_templates import templates
from app.schemas.documents import DocumentRead
from app.services.ai_logging import LoggedAIClient
from app.services.public_ingestion import ingest_upload, ingest_url

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    post_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: LoggedAIClient = Depends(get_ai_client),
    workspace: Workspace = Depends(get_current_workspace),
) -> Document:
    post = db.get(Post, post_id) if post_id else None
    if post_id and post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    try:
        document = await ingest_upload(
            db=db,
            settings=settings,
            ai_client=ai_client,
            file=file,
            workspace=workspace,
            post=post,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.refresh(document)
    if request.headers.get("hx-request") == "true":
        return templates.TemplateResponse(
            request,
            "partials/source_added.html",
            {"document": document, "source_kind": "file"},
            status_code=status.HTTP_201_CREATED,
        )
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return document


@router.post("/url", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def add_url_document(
    request: Request,
    url: str = Form(...),
    post_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: LoggedAIClient = Depends(get_ai_client),
    workspace: Workspace = Depends(get_current_workspace),
) -> Document:
    post = db.get(Post, post_id) if post_id else None
    if post_id and post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    try:
        document = await ingest_url(
            db=db,
            settings=settings,
            ai_client=ai_client,
            url=url,
            workspace=workspace,
            post=post,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.refresh(document)
    if request.headers.get("hx-request") == "true":
        return templates.TemplateResponse(
            request,
            "partials/source_added.html",
            {"document": document, "source_kind": "website"},
            status_code=status.HTTP_201_CREATED,
        )
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return document
