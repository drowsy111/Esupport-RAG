from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.retrieval import EvidenceSource, SearchRequest


class ChatRequest(SearchRequest):
    """
    聊天请求模型，继承自搜索请求模型，增加了会话ID。

    属性:
    - conversation_id: 会话ID
    """ 
    conversation_id: str | None = None


class EvidenceClaim(BaseModel):
    """
    证据主张模型，用于描述生成回答中引用的证据主张。

    属性:
    - text: 证据主张的文本内容
    - citation_ids: 相关的引用ID列表
    """
    text: str = Field(min_length=1, max_length=1200)
    citation_ids: list[str] = Field(min_length=1, max_length=10)


class GeneratedAnswer(BaseModel):
    """
    生成回答模型，用于描述聊天接口生成的回答内容。

    属性:
    - status: 回答状态，包括已回答、需澄清、证据不足或寒暄引导
    - claims: 相关的证据主张列表
    - message: 回答的文本信息
    """
    status: Literal["answered", "insufficient_evidence", "needs_clarification", "smalltalk"]
    claims: list[EvidenceClaim] = Field(default_factory=list, max_length=8)
    message: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_status_content(self):
        if self.status == "answered" and not self.claims:
            raise ValueError("answered status requires at least one claim")
        if self.status != "answered" and self.claims:
            raise ValueError("non-answered status cannot include claims")
        return self


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
    """
    聊天响应模型，用于描述聊天接口的响应信息。

    属性:
    - request_id: 请求ID
    - conversation_id: 会话ID
    - status: 响应状态
    - answer: 生成的回答
    - citations: 引用的证据列表
    - trace: 调试追踪信息
    """
    request_id: str
    conversation_id: str
    status: str
    answer: str
    citations: list[Citation]
    trace: dict
