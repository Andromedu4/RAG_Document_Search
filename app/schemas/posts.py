from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    body: str = Field(default="", max_length=200_000)
    status: str = "published"
    tags: list[str] = []


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    body: str | None = Field(default=None, max_length=200_000)
    status: str | None = None
    tags: list[str] | None = None


class PostRead(BaseModel):
    id: int
    title: str
    slug: str
    body: str
    status: str
    author_id: int
    created_at: datetime
    updated_at: datetime
    tags: list[str] = []

    model_config = {"from_attributes": True}
