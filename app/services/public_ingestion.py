from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.db.models import Document, Post, User
from app.services.ai_logging import LoggedAIClient
from app.services.document_extraction import extract_text_from_upload
from app.services.indexing import index_document
from app.services.text import stable_hash

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


async def ingest_upload(
    *,
    db: Session,
    settings: Settings,
    ai_client: LoggedAIClient,
    file: UploadFile,
    post: Post | None = None,
) -> Document:
    public_user = ensure_public_user(db)
    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    content_hash = stable_hash(content)
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{content_hash[:16]}-{Path(file.filename or 'upload').name}"
    storage_path = upload_dir / safe_name
    storage_path.write_bytes(content)

    document = Document(
        post_id=post.id if post else None,
        uploaded_by_id=public_user.id,
        original_filename=file.filename or "upload",
        content_type=content_type,
        storage_path=str(storage_path),
        extracted_text="",
        content_hash=content_hash,
        processing_status="processing",
    )
    db.add(document)
    db.flush()

    document.extracted_text = extract_text_from_upload(
        content,
        filename=document.original_filename,
        content_type=content_type,
    )
    index_document(db, document, settings, ai_client)
    document.processing_status = "completed"
    db.flush()
    return document
