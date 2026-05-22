import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import PromptRun, RagRun
from app.services.ai_logging import LoggedAIClient
from app.services.prompts import get_active_prompt
from app.services.search import SearchResult, semantic_search


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[dict]
    retrieved: list[SearchResult]
    rag_run_id: int


def answer_question(
    db: Session,
    *,
    question: str,
    query_embedding: list[float],
    settings: Settings,
    ai_client: LoggedAIClient,
) -> RagAnswer:
    retrieved = semantic_search(
        db,
        query_embedding=query_embedding,
        embedding_model=settings.openai_embedding_model,
        limit=settings.rag_top_k,
    )

    if not retrieved:
        answer = "I don't know based on the provided context."
        rag_run = RagRun(question=question, answer=answer, retrieved_chunk_ids=[], citations=[])
        db.add(rag_run)
        db.flush()
        return RagAnswer(answer=answer, citations=[], retrieved=[], rag_run_id=rag_run.id)

    prompt_template = get_active_prompt(db, "rag.answer")
    context = _format_context(retrieved)
    prompt_input = prompt_template.template.format(question=question, context=context)
    generation = ai_client.generate_rag_answer(
        instructions=prompt_template.instructions,
        input_text=prompt_input,
    )
    provider_log_id = ai_client.last_log.id if ai_client.last_log else None
    citations = _citations_from_answer(generation.text, retrieved)

    prompt_run = PromptRun(
        prompt_template_id=prompt_template.id,
        provider_call_log_id=provider_log_id,
        purpose="rag_answer",
        input_payload={"question": question, "chunk_ids": [item.chunk_id for item in retrieved]},
        output_text=generation.text,
    )
    db.add(prompt_run)
    rag_run = RagRun(
        question=question,
        answer=generation.text,
        retrieved_chunk_ids=[item.chunk_id for item in retrieved],
        citations=citations,
        prompt_template_id=prompt_template.id,
        provider_call_log_id=provider_log_id,
    )
    db.add(rag_run)
    db.flush()
    return RagAnswer(
        answer=generation.text,
        citations=citations,
        retrieved=retrieved,
        rag_run_id=rag_run.id,
    )


def _format_context(results: list[SearchResult]) -> str:
    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        lines.append(
            f"[S{index}] {result.title} / {result.source_label} "
            f"(chunk_id={result.chunk_id}, distance={result.distance:.4f})\n"
            f"{result.snippet}"
        )
    return "\n\n".join(lines)


def _citations_from_answer(answer: str, results: list[SearchResult]) -> list[dict]:
    markers = {int(match) for match in re.findall(r"\[S(\d+)\]", answer)}
    citations: list[dict] = []
    for marker in sorted(markers):
        if 1 <= marker <= len(results):
            result = results[marker - 1]
            citations.append(
                {
                    "marker": f"S{marker}",
                    "chunk_id": result.chunk_id,
                    "post_id": result.post_id,
                    "document_id": result.document_id,
                    "title": result.title,
                    "source_label": result.source_label,
                    "snippet": result.snippet[:240],
                }
            )
    return citations
