from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: int
    workspace_id: int | None
    post_id: int | None
    original_filename: str
    content_type: str
    storage_path: str | None
    extracted_text: str
    processing_status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
