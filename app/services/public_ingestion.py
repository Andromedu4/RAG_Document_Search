from collections.abc import Callable
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.db.models import Document, Post, User, Workspace
from app.db.session import SessionLocal
from app.services.ai_logging import LoggedAIClient
from app.services.ai_provider import build_ai_provider
from app.services.document_extraction import extract_text_from_upload
from app.services.indexing import index_document
from app.services.text import stable_hash
from app.services.web_extraction import fetch_web_page

PUBLIC_USER_EMAIL = "anonymous@rag-document-search.local"


def ensure_public_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == PUBLIC_USER_EMAIL))
    if user is not None:
        return user
    user = User(
        email=PUBLIC_USER_EMAIL,
        hashed_password=hash_password("anonymous-user-not-for-login"),
        role="editor",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


async def queue_upload(
    *,
    db: Session,
    settings: Settings,
    file: UploadFile,
    workspace: Workspace,
    post: Post | None = None,
) -> Document:
    public_user = ensure_public_user(db)
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes / 1_000_000
        raise ValueError(f"File is too large. Maximum upload size is {max_mb:.0f} MB.")
    content_type = file.content_type or "application/octet-stream"
    content_hash = stable_hash(content)
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{content_hash[:16]}-{Path(file.filename or 'upload').name}"
    storage_path = upload_dir / safe_name
    storage_path.write_bytes(content)

    document = Document(
        workspace_id=workspace.id,
        post_id=post.id if post else None,
        uploaded_by_id=public_user.id,
        original_filename=file.filename or "upload",
        content_type=content_type,
        storage_path=str(storage_path),
        extracted_text="",
        content_hash=content_hash,
        processing_status="queued",
    )
    db.add(document)
    db.flush()
    return document


def queue_url(
    *,
    db: Session,
    url: str,
    workspace: Workspace,
    post: Post | None = None,
) -> Document:
    public_user = ensure_public_user(db)

    document = Document(
        workspace_id=workspace.id,
        post_id=post.id if post else None,
        uploaded_by_id=public_user.id,
        original_filename=url[:255],
        content_type="text/html",
        storage_path=url,
        extracted_text="",
        content_hash=stable_hash(url),
        processing_status="queued",
    )
    db.add(document)
    db.flush()
    return document


def process_document_background(
    document_id: int,
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    settings = Settings()
    db = session_factory()
    provider = build_ai_provider(settings)
    ai_client = LoggedAIClient(db=db, settings=settings, provider=provider)
    try:
        document = db.get(Document, document_id)
        if document is None:
            return

        if document.storage_path and document.storage_path.startswith(("http://", "https://")):
            _process_url_document(db, document, settings)
        else:
            _process_file_document(db, document)

        document.processing_status = "indexing"
        document.error_message = None
        db.commit()

        index_document(db, document, settings, ai_client)
        document.processing_status = "completed"
        document.error_message = None
        db.commit()
    except Exception as exc:
        db.rollback()
        failed_document = db.get(Document, document_id)
        if failed_document is not None:
            failed_document.processing_status = "failed"
            failed_document.error_message = str(exc)[:2000]
            db.commit()
    finally:
        db.close()


def _process_file_document(db: Session, document: Document) -> None:
    if not document.storage_path:
        raise ValueError("Uploaded file path is missing.")

    document.processing_status = "extracting"
    db.commit()

    content = Path(document.storage_path).read_bytes()
    document.extracted_text = extract_text_from_upload(
        content,
        filename=document.original_filename,
        content_type=document.content_type,
    )
    if not document.extracted_text.strip():
        raise ValueError("No readable text was found in this file.")
    db.commit()


def _process_url_document(db: Session, document: Document, settings: Settings) -> None:
    if not document.storage_path:
        raise ValueError("URL is missing.")

    document.processing_status = "fetching"
    db.commit()

    import asyncio

    web_page = asyncio.run(fetch_web_page(document.storage_path, settings))
    document.original_filename = web_page.title[:255]
    document.content_type = web_page.content_type
    document.storage_path = web_page.url
    document.extracted_text = web_page.text
    document.content_hash = stable_hash(f"{web_page.url}\n{web_page.text}")
    if not document.extracted_text.strip():
        raise ValueError("No readable text was found on this page.")
    db.commit()
