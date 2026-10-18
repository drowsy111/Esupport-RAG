from pydantic import BaseModel, ConfigDict, Field

from app.schemas.query_context import QueryContext


class SearchRequest(BaseModel):
    """
    搜索请求模型，用于描述搜索请求的相关信息。

    属性:
    - query: 搜索查询字符串
    - knowledge_base_id: 知识库ID
    - context: 查询上下文
    """
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    knowledge_base_id: str | None = None
    context: QueryContext = Field(default_factory=QueryContext)


class EvidenceSource(BaseModel):
    """
    证据来源模型，用于描述搜索结果中的证据来源信息。

    属性:
    - chunk_id: 文档块ID
    - content_hash: 内容哈希值
    - text: 文本内容
    - page: 页码
    - anchor: 锚点
    - title_path: 标题路径
    - chunk_index: 文档块索引
    - token_count: 令牌数量
    - structure: 结构化信息
    """
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

