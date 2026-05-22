from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import ALL_ROLES, get_ai_client, get_current_user, require_roles
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import Document, Post, User
from app.db.session import get_db
from app.main_templates import templates
from app.services.ai_logging import LoggedAIClient
from app.services.indexing import index_post
from app.services.text import slugify

router = APIRouter(tags=["ui"])


@router.get("/", response_class=HTMLResponse)
def rag_document_search_home(
    request: Request,
    db: Session = Depends(get_db),
):
    documents = db.scalars(
        select(Document)
        .options(selectinload(Document.chunks))
        .order_by(Document.created_at.desc())
        .limit(12)
    ).all()
    return templates.TemplateResponse(
        request,
        "rag_document_search.html",
        {"documents": documents},
    )


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"roles": sorted(ALL_ROLES)})


@router.post("/register", response_class=HTMLResponse)
def register_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("reader"),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(User).where(User.email == email.lower()))
    if existing:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "roles": sorted(ALL_ROLES),
                "error": "Email already registered.",
            },
            status_code=status.HTTP_409_CONFLICT,
        )
    user_count = db.scalar(select(func.count(User.id))) or 0
    selected_role = role if role in ALL_ROLES else "reader"
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        role="admin" if user_count == 0 else selected_role,
    )
    db.add(user)
    db.commit()
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
def login_form(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = db.scalar(select(User).where(User.email == username.lower()))
    if user is None or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Incorrect email or password."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    token = create_access_token(subject=str(user.id), settings=settings, extra_claims={"role": user.role})
    redirect = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie("access_token", token, httponly=True, samesite="lax")
    return redirect


@router.get("/logout")
def logout():
    redirect = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie("access_token")
    return redirect


@router.get("/posts/new", response_class=HTMLResponse)
def new_post_page(request: Request, current_user: User = Depends(require_roles("admin", "editor"))):
    return templates.TemplateResponse(
        request,
        "post_form.html",
        {"current_user": current_user},
    )


@router.post("/posts/new")
def create_post_form(
    title: str = Form(...),
    body: str = Form(...),
    status_value: str = Form("published", alias="status"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: LoggedAIClient = Depends(get_ai_client),
    current_user: User = Depends(require_roles("admin", "editor")),
):
    post = Post(
        title=title,
        slug=_unique_slug(db, title),
        body=body,
        status=status_value,
        author_id=current_user.id,
    )
    db.add(post)
    db.flush()
    index_post(db, post, settings, ai_client)
    db.commit()
    return RedirectResponse(f"/posts/{post.id}/view", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/posts/{post_id}/view", response_class=HTMLResponse)
def post_detail_page(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.scalar(
        select(Post)
        .options(selectinload(Post.documents), selectinload(Post.chunks))
        .where(Post.id == post_id)
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return templates.TemplateResponse(
        request,
        "post_detail.html",
        {"current_user": current_user, "post": post},
    )


def _unique_slug(db: Session, title: str) -> str:
    base = slugify(title)
    slug = base
    suffix = 2
    while db.scalar(select(Post).where(Post.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
