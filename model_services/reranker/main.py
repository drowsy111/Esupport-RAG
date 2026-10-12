from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from model_services.common import require_model_key
from model_services.reranker.scorer import Scorer


@asynccontextmanager
async def lifespan(app):
    app.state.scorer = Scorer(get_settings())
    yield


app = FastAPI(title="Reranker", lifespan=lifespan)


class RerankRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    texts: list[str] = Field(min_length=1, max_length=200)


@app.get("/health/live")
def live():
    return {"status": "ok", "model_loaded": hasattr(app.state, "scorer")}


@app.post("/rerank", dependencies=[Depends(require_model_key)])
def rerank(body: RerankRequest):
    if any(len(text) > 40000 for text in body.texts):
        raise HTTPException(422, "Candidate text is too large")
    return {"scores": app.state.scorer.score(body.query, body.texts)}

