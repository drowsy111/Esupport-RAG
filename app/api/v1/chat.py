from fastapi import APIRouter, Depends, Request

from app.api.dependencies import (
    current_principal, get_resources, get_session, get_settings_dependency,
)
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/completions", response_model=ChatResponse)
def complete(
    body: ChatRequest, request: Request, session=Depends(get_session),
    principal=Depends(current_principal), resources=Depends(get_resources),
    settings=Depends(get_settings_dependency),
):
    return chat(session, principal, resources, settings, body, request.state.request_id)

