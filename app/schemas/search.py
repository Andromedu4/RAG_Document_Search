from pydantic import BaseModel


class SearchItem(BaseModel):
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


class SearchResponse(BaseModel):
    query: str
    results: list[SearchItem]
