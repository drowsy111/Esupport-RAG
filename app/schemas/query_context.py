from pydantic import BaseModel, ConfigDict, Field


class QueryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: str | None = Field(default=None, max_length=100)
    product_version: str | None = Field(default=None, max_length=50)
    deployment_mode: str | None = Field(default=None, max_length=50)

