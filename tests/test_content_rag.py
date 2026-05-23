import time

from app.db.models import PostChunk, ProviderCallLog
from app.services.web_extraction import WebPageContent

from .conftest import auth_headers, make_docx_bytes, register_and_login


def wait_for_status_text(client, expected: str, timeout: float = 5.0) -> str:
    deadline = time.monotonic() + timeout
    last_text = ""
    while time.monotonic() < deadline:
        status = client.get("/documents/status", headers={"HX-Request": "true", "Accept": "text/html"})
        assert status.status_code == 200
        last_text = status.text
        if expected in last_text:
            return last_text
        time.sleep(0.05)
    return last_text


def test_post_create_indexes_chunks_and_semantic_search(client, db_session):
    token = register_and_login(client)

    response = client.post(
        "/posts",
        json={
            "title": "Semantic Retrieval Architecture",
            "body": "Semantic retrieval uses embeddings and pgvector to find relevant knowledge chunks.",
            "tags": ["RAG", "Search"],
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert db_session.query(PostChunk).count() >= 1

    search = client.get(
        "/search/semantic",
        params={"q": "semantic retrieval embeddings"},
        headers=auth_headers(token),
    )

    assert search.status_code == 200
    payload = search.json()
    assert payload["results"]
    assert payload["results"][0]["title"] == "Semantic Retrieval Architecture"

    html_search = client.get(
        "/search/semantic",
        params={"q": "semantic retrieval embeddings"},
        headers={"HX-Request": "true", "Accept": "text/html"},
    )

    assert html_search.status_code == 200
    assert "Semantic Retrieval Architecture" in html_search.text
    assert "source-snippet" in html_search.text


def test_public_upload_and_rag_question_without_login(client):
    upload = client.post(
        "/documents/upload",
        files={
            "file": (
                "refund-policy.txt",
                b"Refund requests must include the order id and reason for the refund.",
                "text/plain",
            )
        },
    )

    assert upload.status_code == 201
    assert upload.json()["processing_status"] == "queued"

    response = client.post(
        "/rag/ask",
        json={"question": "What must refund requests include?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["relevant_documents"]
    assert payload["pipeline"] == [
        "indexing",
        "question",
        "retrieval",
        "generation",
        "answer",
    ]


def test_workspace_cookie_isolates_public_rag_sources(client):
    client.post(
        "/documents/upload",
        files={
            "file": (
                "private-refund-policy.txt",
                b"Private workspace refund requests require approval from finance.",
                "text/plain",
            )
        },
    )

    first_workspace_answer = client.post(
        "/rag/ask",
        json={"question": "Who approves private workspace refund requests?"},
    )
    assert first_workspace_answer.status_code == 200
    assert first_workspace_answer.json()["relevant_documents"]

    client.cookies.clear()
    isolated_answer = client.post(
        "/rag/ask",
        json={"question": "Who approves private workspace refund requests?"},
    )

    assert isolated_answer.status_code == 200
    assert isolated_answer.json()["relevant_documents"] == []
    assert "don't know" in isolated_answer.json()["answer"].lower()


def test_clear_workspace_removes_visible_sources(client):
    client.post(
        "/documents/upload",
        files={
            "file": (
                "clear-me.txt",
                b"Workspace clearing should remove this searchable source.",
                "text/plain",
            )
        },
    )

    before_clear = client.get("/search/semantic", params={"q": "workspace clearing"})
    assert before_clear.status_code == 200
    assert before_clear.json()["results"]

    clear_response = client.post("/workspace/clear", follow_redirects=False)
    assert clear_response.status_code == 303

    after_clear = client.get("/search/semantic", params={"q": "workspace clearing"})
    assert after_clear.status_code == 200
    assert after_clear.json()["results"] == []


def test_public_url_ingestion_becomes_rag_source(client, monkeypatch):
    async def fake_fetch_web_page(url, settings):
        return WebPageContent(
            url=url,
            title="Remote Refund Policy",
            content_type="text/html",
            text="Remote refund policy says refund requests need the customer email and invoice number.",
        )

    monkeypatch.setattr("app.services.public_ingestion.fetch_web_page", fake_fetch_web_page)

    upload = client.post(
        "/documents/url",
        data={"url": "https://example.com/refund-policy"},
    )

    assert upload.status_code == 201
    payload = upload.json()
    assert payload["original_filename"] == "https://example.com/refund-policy"
    assert payload["storage_path"] == "https://example.com/refund-policy"
    assert payload["processing_status"] == "queued"

    response = client.post(
        "/rag/ask",
        json={"question": "What does the remote refund policy require?"},
    )

    assert response.status_code == 200
    answer = response.json()
    assert answer["relevant_documents"]
    assert answer["relevant_documents"][0]["source_url"] == "https://example.com/refund-policy"


def test_async_url_ingestion_returns_partial_not_full_page(client, monkeypatch):
    async def fake_fetch_web_page(url, settings):
        return WebPageContent(
            url=url,
            title="DOU Gift Mall Vacancy",
            content_type="text/html",
            text="Gift Mall vacancy mentions Python, FastAPI, RAG, and document search responsibilities.",
        )

    monkeypatch.setattr("app.services.public_ingestion.fetch_web_page", fake_fetch_web_page)

    response = client.post(
        "/documents/url",
        data={
            "url": "https://jobs.dou.ua/companies/gift-mall/vacancies/355724/?from=widget_hot_category;"
        },
        headers={"HX-Request": "true", "Accept": "text/html"},
    )

    assert response.status_code == 201
    assert "Сайт принят в обработку" in response.text
    assert "<!doctype html>" not in response.text.lower()
    assert "<html" not in response.text.lower()

    status_text = wait_for_status_text(client, "DOU Gift Mall Vacancy")
    assert "ready" in status_text


def test_rag_answer_has_citation_and_logs_cost(client, db_session):
    token = register_and_login(client)
    client.post(
        "/posts",
        json={
            "title": "RAG Citation Policy",
            "body": "RAG answers must cite retrieved sources and say they do not know when context is missing.",
        },
        headers=auth_headers(token),
    )

    response = client.post(
        "/rag/ask",
        json={"question": "How should RAG answers cite sources?"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert "[S1]" in payload["answer"]
    assert payload["citations"]
    logs = db_session.query(ProviderCallLog).all()
    assert {log.operation for log in logs} >= {"embedding", "rag_answer"}
    assert all(log.estimated_cost_usd is not None for log in logs)

    html_response = client.post(
        "/rag/ask",
        data={"question": "How should RAG answers cite sources?"},
        headers={"HX-Request": "true", "Accept": "text/html"},
    )

    assert html_response.status_code == 200
    assert "Использованные источники" in html_response.text
    assert "source-snippet" in html_response.text
    assert "Relevant documents" not in html_response.text
    assert ">retrieved context<" not in html_response.text


def test_docx_upload_extracts_text_and_becomes_searchable(client, db_session):
    token = register_and_login(client)
    post = client.post(
        "/posts",
        json={"title": "Document Parent", "body": "Parent article."},
        headers=auth_headers(token),
    ).json()
    content = make_docx_bytes("Expense policy requires receipts for travel reimbursements.")

    upload = client.post(
        "/documents/upload",
        data={"post_id": str(post["id"])},
        files={
            "file": (
                "expense-policy.docx",
                content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=auth_headers(token),
    )

    assert upload.status_code == 201
    assert upload.json()["processing_status"] == "queued"

    search = client.get(
        "/search/semantic",
        params={"q": "travel receipts reimbursement"},
        headers=auth_headers(token),
    )

    assert search.status_code == 200
    assert any("expense-policy.docx" in item["source_label"] for item in search.json()["results"])
