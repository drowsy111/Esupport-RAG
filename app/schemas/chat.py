from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.retrieval import EvidenceSource, SearchRequest


class ChatRequest(SearchRequest):
    conversation_id: str | None = None


class EvidenceClaim(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    citation_ids: list[str] = Field(min_length=1, max_length=10)


class GeneratedAnswer(BaseModel):
    status: Literal["answered", "insufficient_evidence", "needs_clarification"]
    claims: list[EvidenceClaim] = Field(default_factory=list, max_length=20)
    message: str = Field(default="", max_length=2000)


class Citation(BaseModel):
    citation_id: str
    document_id: str
    document_name: str
    revision: int
    chunk_id: str
    page: int | None
    anchor: str
    quote: str
    source_kind: str
    matched_text: str = ""
    matched_chunk_ids: list[str] = Field(default_factory=list)
    sources: list[EvidenceSource] = Field(default_factory=list)


class ChatResponse(BaseModel):
    request_id: str
    conversation_id: str
    status: str
    answer: str
    citations: list[Citation]
    trace: dict

