from app.db.models import User

from .conftest import auth_headers, register_and_login


def test_unauthenticated_root_renders_public_rag_workspace(client):
    response = client.get("/", follow_redirects=True)

    assert response.status_code == 200
    assert "RAG for Document Search" in response.text
    assert "Загрузить файл" in response.text
    assert "Добавить сайт в базу знаний" in response.text
    assert 'data-async-form="true"' in response.text
    assert 'data-action-url="/documents/url"' in response.text
    assert 'data-action-url="/rag/ask"' in response.text


def test_semantic_search_page_uses_async_search_form(client):
    response = client.get("/search")

    assert response.status_code == 200
    assert 'data-async-form="true"' in response.text
    assert 'data-method="GET"' in response.text
    assert 'data-action-url="/search/semantic"' in response.text


def test_register_login_and_me(client):
    token = register_and_login(client, email="recruiter@example.com", role="reader")

    response = client.get("/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["email"] == "recruiter@example.com"
    assert response.json()["role"] == "admin"


def test_reader_cannot_create_posts(client):
    register_and_login(client, email="admin@example.com", role="admin")
    token = register_and_login(client, email="reader@example.com", role="reader")

    response = client.post(
        "/posts",
        json={"title": "Reader Post", "body": "Readers should not write."},
        headers=auth_headers(token),
    )

    assert response.status_code == 403


def test_passwords_are_hashed(db_session, client):
    register_and_login(client, email="hash@example.com", password="password123")
    user = db_session.query(User).filter_by(email="hash@example.com").one()

    assert user.hashed_password != "password123"
    assert user.hashed_password.startswith("$2")
