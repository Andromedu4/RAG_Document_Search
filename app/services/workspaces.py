import secrets

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Document, PostChunk, RagRun, Workspace

WORKSPACE_COOKIE_NAME = "rag_workspace_id"
WORKSPACE_COOKIE_MAX_AGE = 60 * 60 * 24 * 14


def get_workspace_by_public_id(db: Session, public_id: str | None) -> Workspace | None:
    if not public_id:
        return None
    if len(public_id) > 96:
        return None
    return db.scalar(select(Workspace).where(Workspace.public_id == public_id))


def create_workspace(db: Session) -> Workspace:
    while True:
        public_id = secrets.token_urlsafe(24)
        if get_workspace_by_public_id(db, public_id) is None:
            workspace = Workspace(public_id=public_id)
            db.add(workspace)
            db.flush()
            return workspace


def ensure_workspace(db: Session, public_id: str | None) -> tuple[Workspace, bool]:
    workspace = get_workspace_by_public_id(db, public_id)
    if workspace is not None:
        return workspace, False
    return create_workspace(db), True


def set_workspace_cookie(response: Response, public_id: str) -> None:
    response.set_cookie(
        WORKSPACE_COOKIE_NAME,
        public_id,
        max_age=WORKSPACE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def clear_workspace_data(db: Session, workspace: Workspace) -> None:
    db.execute(delete(PostChunk).where(PostChunk.workspace_id == workspace.id))
    db.execute(delete(Document).where(Document.workspace_id == workspace.id))
    db.execute(delete(RagRun).where(RagRun.workspace_id == workspace.id))
    db.delete(workspace)
    db.flush()
