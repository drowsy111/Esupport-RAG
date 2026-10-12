from pydantic import BaseModel, Field


class ParsedBlock(BaseModel):
    text: str
    title_path: str = ""
    page: int | None = None
    anchor: str = ""
    starts_section: bool = False


class ParsedDocument(BaseModel):
    blocks: list[ParsedBlock]
    warnings: list[str] = Field(default_factory=list)

