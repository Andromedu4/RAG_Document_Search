from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import PromptTemplate

DEFAULT_RAG_INSTRUCTIONS = """You answer questions for an internal knowledge base.
Use only the retrieved context supplied in the prompt.
If the context does not contain the answer, say "I don't know based on the provided context."
Cite every factual claim with the source marker like [S1] or [S2]."""

DEFAULT_RAG_TEMPLATE = """Question:
{question}

Retrieved context:
{context}

Answer with citations:"""


def ensure_default_prompts(db: Session) -> None:
    existing = db.scalar(
        select(PromptTemplate).where(
            PromptTemplate.name == "rag.answer",
            PromptTemplate.version == "v1",
        )
    )
    if existing:
        return
    db.add(
        PromptTemplate(
            name="rag.answer",
            version="v1",
            description="Default grounded RAG answer prompt.",
            instructions=DEFAULT_RAG_INSTRUCTIONS,
            template=DEFAULT_RAG_TEMPLATE,
            is_active=True,
        )
    )
    db.commit()


def get_active_prompt(db: Session, name: str) -> PromptTemplate:
    prompt = db.scalar(
        select(PromptTemplate)
        .where(PromptTemplate.name == name, PromptTemplate.is_active.is_(True))
        .order_by(PromptTemplate.created_at.desc())
    )
    if prompt is None:
        ensure_default_prompts(db)
        prompt = db.scalar(
            select(PromptTemplate)
            .where(PromptTemplate.name == name, PromptTemplate.is_active.is_(True))
            .order_by(PromptTemplate.created_at.desc())
        )
    if prompt is None:
        raise RuntimeError(f"No active prompt template found for {name}")
    return prompt


def activate_prompt(db: Session, prompt: PromptTemplate) -> None:
    db.execute(
        update(PromptTemplate)
        .where(PromptTemplate.name == prompt.name, PromptTemplate.id != prompt.id)
        .values(is_active=False)
    )
    prompt.is_active = True
    db.flush()
