from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document, Post, PostChunk
from app.services.ai_logging import LoggedAIClient
from app.services.chunking import chunk_text
from app.services.text import estimate_tokens, stable_hash


def index_post(db: Session, post: Post, settings: Settings, ai_client: LoggedAIClient) -> list[PostChunk]:
    post.content_hash = stable_hash(post.body)
    return _index_source(
        db,
        settings=settings,
        ai_client=ai_client,
        source_type="post",
        source_label=post.title,
        text=post.body,
        post=post,
        document=None,
    )


def index_document(
    db: Session, document: Document, settings: Settings, ai_client: LoggedAIClient
) -> list[PostChunk]:
    return _index_source(
        db,
        settings=settings,
        ai_client=ai_client,
        source_type="document",
        source_label=document.original_filename,
        text=document.extracted_text,
        post=document.post,
        document=document,
    )


def _index_source(
    db: Session,
    *,
    settings: Settings,
    ai_client: LoggedAIClient,
    source_type: str,
    source_label: str,
    text: str,
    post: Post | None,
    document: Document | None,
) -> list[PostChunk]:
    chunks = chunk_text(
        text,
        max_chars=settings.chunk_max_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )
    post_id = post.id if post else None
    document_id = document.id if document else None

    existing = {
        chunk.content_hash: chunk
        for chunk in db.scalars(
            select(PostChunk).where(
                PostChunk.source_type == source_type,
                PostChunk.post_id.is_(post_id) if post_id is None else PostChunk.post_id == post_id,
                PostChunk.document_id.is_(document_id)
                if document_id is None
                else PostChunk.document_id == document_id,
                PostChunk.embedding_model == settings.openai_embedding_model,
            )
        )
    }

    new_hashes = {chunk.content_hash for chunk in chunks}
    if existing:
        obsolete_ids = [chunk.id for hash_, chunk in existing.items() if hash_ not in new_hashes]
        if obsolete_ids:
            db.execute(delete(PostChunk).where(PostChunk.id.in_(obsolete_ids)))

    indexed_chunks: list[PostChunk] = []
    needs_embedding: list[PostChunk] = []
    for text_chunk in chunks:
        chunk = existing.get(text_chunk.content_hash)
        if chunk is None:
            chunk = PostChunk(
                post_id=post_id,
                document_id=document_id,
                source_type=source_type,
                source_label=source_label,
                chunk_index=text_chunk.index,
                content=text_chunk.content,
                content_hash=text_chunk.content_hash,
                token_count=estimate_tokens(text_chunk.content),
                embedding_model=settings.openai_embedding_model,
            )
            db.add(chunk)
            needs_embedding.append(chunk)
        else:
            chunk.chunk_index = text_chunk.index
            chunk.content = text_chunk.content
            chunk.source_label = source_label
            chunk.token_count = estimate_tokens(text_chunk.content)
        indexed_chunks.append(chunk)

    db.flush()
    if needs_embedding:
        embedding_result = ai_client.embed_texts([chunk.content for chunk in needs_embedding])
        for chunk, embedding in zip(needs_embedding, embedding_result.embeddings, strict=True):
            chunk.embedding = embedding
            chunk.embedding_model = embedding_result.model
    db.flush()
    return indexed_chunks
