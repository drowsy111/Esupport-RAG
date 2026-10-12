from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from model_services.common import require_model_key
from model_services.embedding.encoder import Encoder


@asynccontextmanager
async def lifespan(app):
    app.state.encoder = Encoder(get_settings())
    yield


app = FastAPI(title="BGE-M3 Embedding", lifespan=lifespan)


class EncodeRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=16)


@app.get("/health/live")
def live():
    return {"status": "ok", "model_loaded": hasattr(app.state, "encoder")}


@app.post("/embed/documents", dependencies=[Depends(require_model_key)])
@app.post("/embed/queries", dependencies=[Depends(require_model_key)])
def encode(body: EncodeRequest):
    if any(not text.strip() or len(text) > 40000 for text in body.texts):
        raise HTTPException(422, "Texts must be nonempty and at most 40000 characters")
    try:
        items = app.state.encoder.encode(body.texts)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"embedding_version": get_settings().embedding_version, "items": items}

