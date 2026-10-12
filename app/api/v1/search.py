from fastapi import APIRouter, Depends

from app.api.dependencies import (
    current_principal, get_resources, get_session, get_settings_dependency,
)
from app.schemas.retrieval import SearchRequest
from app.services.retrieval_service import retrieve, revalidate

router = APIRouter(tags=["search"])


@router.post("/search")
def search(
    body: SearchRequest, session=Depends(get_session), principal=Depends(current_principal),
    resources=Depends(get_resources), settings=Depends(get_settings_dependency),
):
    candidates, trace = retrieve(session, principal, resources, settings, body)
    valid = {c.chunk_id for c in revalidate(session, principal, candidates, body.context)}
    return {"candidates": [c for c in candidates if c.chunk_id in valid], "trace": trace}

