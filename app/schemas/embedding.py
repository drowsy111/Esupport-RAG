import math

from pydantic import BaseModel, Field, field_validator


class EmbeddingItem(BaseModel):
    dense: list[float] = Field(min_length=1024, max_length=1024)
    sparse: dict[int, float]

    @field_validator("dense")
    @classmethod
    def dense_finite(cls, values):
        if not all(math.isfinite(v) for v in values):
            raise ValueError("non-finite dense vector")
        return values

    @field_validator("sparse")
    @classmethod
    def sparse_valid(cls, values):
        if any(k < 0 or not math.isfinite(v) or v < 0 for k, v in values.items()):
            raise ValueError("invalid sparse vector")
        return {k: v for k, v in values.items() if v > 0}

