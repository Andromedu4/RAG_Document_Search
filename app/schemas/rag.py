from pydantic import BaseModel, Field


class RagAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=5000)


class RelevantDocument(BaseModel):
    chunk_id: int
    post_id: int | None
    document_id: int | None
    title: str
    source_label: str
    snippet: str
    distance: float
    score: float
    chunk_index: int


class RagAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[dict]
    retrieved_chunk_ids: list[int]
    rag_run_id: int
    relevant_documents: list[RelevantDocument] = []
    pipeline: list[str] = []
