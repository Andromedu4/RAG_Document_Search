import os
from collections.abc import Generator
from io import BytesIO

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_suite.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-bytes")

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import get_db
from app.main import create_app
from app.services.prompts import ensure_default_prompts


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.info["session_factory"] = TestingSessionLocal
    ensure_default_prompts(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    get_settings.cache_clear()
    app = create_app()
    app.state.db_session_factory = db_session.info["session_factory"]

    def override_get_db() -> Generator[Session, None, None]:
        db_session.expire_all()
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(
    client: TestClient,
    *,
    email: str = "editor@example.com",
    password: str = "password123",
    role: str = "editor",
) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "role": role},
    )
    assert response.status_code in {201, 409}
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_docx_bytes(text: str) -> bytes:
    buffer = BytesIO()
    document = DocxDocument()
    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)
    document.save(buffer)
    return buffer.getvalue()
