from pydantic import BaseModel, ConfigDict, Field

from app.schemas.query_context import QueryContext


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    knowledge_base_id: str | None = None
    context: QueryContext = Field(default_factory=QueryContext)


class EvidenceSource(BaseModel):
    chunk_id: str
    content_hash: str
    text: str
    page: int | None = None
    anchor: str = ""
    title_path: str = ""
    chunk_index: int = 0
    token_count: int = 0
    structure: dict | None = None


class Candidate(BaseModel):
    chunk_id: str
    document_id: str
    version_id: str
    document_name: str
    revision: int
    text: str
    content_hash: str
    page: int | None = None
    anchor: str = ""
    title_path: str = ""
    source_kind: str = "uploaded"
    product_version: str = ""
    fusion_score: float = 0
    rerank_score: float | None = None
    chunk_index: int = 0
    token_count: int = 0
    structure: dict | None = None
    matched_text: str = ""
    matched_chunk_ids: list[str] = Field(default_factory=list)
    sources: list[EvidenceSource] = Field(default_factory=list)

    def as_source(self):
        return EvidenceSource(**self.model_dump(include=set(EvidenceSource.model_fields)))

