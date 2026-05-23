from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_ai_client, get_current_user, get_current_workspace, require_roles
from app.core.config import Settings, get_settings
from app.db.models import Post, Tag, User, Workspace
from app.db.session import get_db
from app.schemas.posts import PostCreate, PostRead, PostUpdate
from app.services.ai_logging import LoggedAIClient
from app.services.indexing import index_post
from app.services.text import slugify, unique_preserve_order

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=list[PostRead])
def list_posts(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[PostRead]:
    posts = db.scalars(
        select(Post)
        .options(selectinload(Post.tags))
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_serialize_post(post) for post in posts]


@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: LoggedAIClient = Depends(get_ai_client),
    current_user: User = Depends(require_roles("admin", "editor")),
    workspace: Workspace = Depends(get_current_workspace),
) -> PostRead:
    post = Post(
        title=payload.title,
        slug=_unique_slug(db, payload.title),
        body=payload.body,
        status=payload.status,
        author_id=current_user.id,
    )
    post.tags = _load_tags(db, payload.tags)
    db.add(post)
    db.flush()
    index_post(db, post, settings, ai_client, workspace_id=workspace.id)
    db.commit()
    db.refresh(post)
    return _serialize_post(post)


@router.get("/{post_id}", response_model=PostRead)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PostRead:
    post = db.scalar(select(Post).options(selectinload(Post.tags)).where(Post.id == post_id))
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return _serialize_post(post)


@router.patch("/{post_id}", response_model=PostRead)
def update_post(
    post_id: int,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: LoggedAIClient = Depends(get_ai_client),
    _: User = Depends(require_roles("admin", "editor")),
    workspace: Workspace = Depends(get_current_workspace),
) -> PostRead:
    post = db.scalar(select(Post).options(selectinload(Post.tags)).where(Post.id == post_id))
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if payload.title is not None and payload.title != post.title:
        post.title = payload.title
        post.slug = _unique_slug(db, payload.title, exclude_id=post.id)
    if payload.body is not None:
        post.body = payload.body
    if payload.status is not None:
        post.status = payload.status
    if payload.tags is not None:
        post.tags = _load_tags(db, payload.tags)
    index_post(db, post, settings, ai_client, workspace_id=workspace.id)
    db.commit()
    db.refresh(post)
    return _serialize_post(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "editor")),
) -> None:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    db.delete(post)
    db.commit()


def _load_tags(db: Session, tag_names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in unique_preserve_order(tag_names):
        tag_slug = slugify(name)
        tag = db.scalar(select(Tag).where(Tag.slug == tag_slug))
        if tag is None:
            tag = Tag(name=name, slug=tag_slug)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def _unique_slug(db: Session, title: str, *, exclude_id: int | None = None) -> str:
    base = slugify(title)
    slug = base
    suffix = 2
    while True:
        statement = select(Post).where(Post.slug == slug)
        if exclude_id is not None:
            statement = statement.where(Post.id != exclude_id)
        if db.scalar(statement) is None:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def _serialize_post(post: Post) -> PostRead:
    return PostRead(
        id=post.id,
        title=post.title,
        slug=post.slug,
        body=post.body,
        status=post.status,
        author_id=post.author_id,
        created_at=post.created_at,
        updated_at=post.updated_at,
        tags=[tag.name for tag in post.tags],
    )
