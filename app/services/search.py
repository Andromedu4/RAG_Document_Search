from dataclasses import dataclass
from math import sqrt
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.db.models import PostChunk


@dataclass(frozen=True)
class SearchResult:
    chunk_id: int
    post_id: int | None
    document_id: int | None
    title: str
    source_label: str
    snippet: str
    distance: float
    score: float
    chunk_index: int
    source_url: str | None = None


def semantic_search(
    db: Session,
    *,
    query_embedding: list[float],
    embedding_model: str,
    limit: int,
    workspace_id: int,
) -> list[SearchResult]:
    if db.bind and db.bind.dialect.name == "postgresql":
        return _postgres_search(
            db,
            query_embedding,
            embedding_model=embedding_model,
            limit=limit,
            workspace_id=workspace_id,
        )
    return _python_search(db, query_embedding, embedding_model=embedding_model, limit=limit, workspace_id=workspace_id)


def _postgres_search(
    db: Session,
    query_embedding: list[float],
    *,
    embedding_model: str,
    limit: int,
    workspace_id: int,
) -> list[SearchResult]:
    vector_literal = "[" + ",".join(f"{value:.8f}" for value in query_embedding) + "]"
    rows = db.execute(
        text(
            """
            SELECT
                pc.id AS chunk_id,
                pc.post_id,
                pc.document_id,
                COALESCE(p.title, pc.source_label) AS title,
                pc.source_label,
                d.storage_path AS source_url,
                pc.content AS snippet,
                pc.embedding <=> CAST(:embedding AS vector) AS distance,
                pc.chunk_index
            FROM post_chunks pc
            LEFT JOIN posts p ON p.id = pc.post_id
            LEFT JOIN documents d ON d.id = pc.document_id
            WHERE pc.embedding IS NOT NULL
              AND pc.embedding_model = :embedding_model
              AND pc.workspace_id = :workspace_id
            ORDER BY pc.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        ),
        {
            "embedding": vector_literal,
            "embedding_model": embedding_model,
            "limit": limit,
            "workspace_id": workspace_id,
        },
    ).mappings()
    return [_row_to_result(row) for row in rows]


def _python_search(
    db: Session,
    query_embedding: list[float],
    *,
    embedding_model: str,
    limit: int,
    workspace_id: int,
) -> list[SearchResult]:
    chunks = (
        db.query(PostChunk)
        .options(joinedload(PostChunk.post), joinedload(PostChunk.document))
        .filter(
            PostChunk.embedding.is_not(None),
            PostChunk.embedding_model == embedding_model,
            PostChunk.workspace_id == workspace_id,
        )
        .all()
    )
    results: list[SearchResult] = []
    for chunk in chunks:
        distance = cosine_distance(query_embedding, chunk.embedding or [])
        title = chunk.post.title if chunk.post else chunk.source_label
        source_url = _public_source_url(chunk.document.storage_path if chunk.document else None)
        results.append(
            SearchResult(
                chunk_id=chunk.id,
                post_id=chunk.post_id,
                document_id=chunk.document_id,
                title=title,
                source_label=chunk.source_label,
                snippet=chunk.content[:500],
                distance=distance,
                score=max(0.0, 1.0 - distance),
                chunk_index=chunk.chunk_index,
                source_url=source_url,
            )
        )
    return sorted(results, key=lambda result: result.distance)[:limit]


def cosine_distance(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 1.0
    return 1.0 - (dot / (left_norm * right_norm))


def _row_to_result(row: dict[str, Any]) -> SearchResult:
    distance = float(row["distance"])
    return SearchResult(
        chunk_id=row["chunk_id"],
        post_id=row["post_id"],
        document_id=row["document_id"],
        title=row["title"],
        source_label=row["source_label"],
        snippet=row["snippet"][:500],
        distance=distance,
        score=max(0.0, 1.0 - distance),
        chunk_index=row["chunk_index"],
        source_url=_public_source_url(row.get("source_url")),
    )


def _public_source_url(value: str | None) -> str | None:
    if value and value.startswith(("http://", "https://")):
        return value
    return None
