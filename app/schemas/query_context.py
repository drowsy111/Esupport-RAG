from pydantic import BaseModel, ConfigDict, Field


class QueryContext(BaseModel):
    """
    查询上下文模型，用于描述产品的相关信息。

    属性:
    - product_id: 产品ID
    - product_version: 产品版本
    - deployment_mode: 部署模式
    """
    model_config = ConfigDict(extra="forbid")
    product_id: str | None = Field(default=None, max_length=100)
    product_version: str | None = Field(default=None, max_length=50)
    deployment_mode: str | None = Field(default=None, max_length=50)

