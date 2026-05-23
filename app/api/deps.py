from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.models import User, Workspace
from app.db.session import get_db
from app.services.ai_logging import LoggedAIClient
from app.services.ai_provider import build_ai_provider
from app.services.workspaces import WORKSPACE_COOKIE_NAME, ensure_workspace

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

WRITER_ROLES = {"admin", "editor"}
ALL_ROLES = {"admin", "editor", "reader"}


def get_current_workspace(
    request: Request,
    db: Session = Depends(get_db),
) -> Workspace:
    cookie_public_id = request.cookies.get(WORKSPACE_COOKIE_NAME)
    workspace, created = ensure_workspace(db, cookie_public_id)
    if created:
        db.commit()
    request.state.workspace_id = workspace.id
    request.state.workspace_public_id = workspace.public_id
    return workspace


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    token = token or request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        token = token.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(token, settings)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        token = token.removeprefix("Bearer ").strip()
    if not token:
        return None
    try:
        payload = decode_access_token(token, settings)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    user = db.get(User, user_id)
    return user if user and user.is_active else None


def require_roles(*roles: str) -> Callable[[User], User]:
    allowed = set(roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency


def get_ai_client(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoggedAIClient:
    provider = build_ai_provider(settings)
    return LoggedAIClient(db=db, settings=settings, provider=provider)
