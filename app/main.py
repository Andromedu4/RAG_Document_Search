from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, auth, documents, posts, rag, search, web
from app.core.config import get_settings
from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.db.sqlite_compat import ensure_sqlite_workspace_schema
from app.services.prompts import ensure_default_prompts
from app.services.workspaces import WORKSPACE_COOKIE_NAME, set_workspace_cookie


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_workspace_schema(engine)
    with SessionLocal() as db:
        ensure_default_prompts(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.state.db_session_factory = SessionLocal
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.middleware("http")
    async def workspace_cookie_middleware(request, call_next):
        response = await call_next(request)
        workspace_public_id = getattr(request.state, "workspace_public_id", None)
        if workspace_public_id and request.cookies.get(WORKSPACE_COOKIE_NAME) != workspace_public_id:
            set_workspace_cookie(response, workspace_public_id)
        return response

    app.include_router(web.router)
    app.include_router(auth.router)
    app.include_router(posts.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(rag.router)
    app.include_router(admin.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
