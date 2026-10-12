from pydantic import BaseModel


class ChunkDraft(BaseModel):
    text: str
    title_path: str
    page: int | None
    anchor: str
    token_count: int
    structure: dict | None = None

