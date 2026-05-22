from app.db.models import PostChunk, ProviderCallLog

from .conftest import auth_headers, make_docx_bytes, register_and_login


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
    assert upload.json()["processing_status"] == "completed"

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
    assert upload.json()["processing_status"] == "completed"

    search = client.get(
        "/search/semantic",
        params={"q": "travel receipts reimbursement"},
        headers=auth_headers(token),
    )

    assert search.status_code == 200
    assert any("expense-policy.docx" in item["source_label"] for item in search.json()["results"])
