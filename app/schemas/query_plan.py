from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal["direct", "decompose", "clarify"]
    sub_queries: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        default_factory=list, max_length=3,
    )
    clarification_message: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def validate_route_payload(self):
        if self.route == "direct" and (self.sub_queries or self.clarification_message):
            raise ValueError("direct route cannot include sub-queries or clarification")
        if self.route == "decompose":
            if not 2 <= len(self.sub_queries) <= 3 or self.clarification_message:
                raise ValueError("decompose route requires two or three sub-queries")
            if len({query.strip() for query in self.sub_queries}) != len(self.sub_queries):
                raise ValueError("sub-queries must be distinct")
        if self.route == "clarify" and (
            not self.clarification_message.strip() or self.sub_queries
        ):
            raise ValueError("clarify route requires a message and no sub-queries")
        return self
