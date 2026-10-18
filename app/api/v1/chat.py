"""
文件说明: 该模块定义了FastAPI应用的聊天相关路由，包括生成聊天回复的接口。
"""
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
    """
    生成聊天回复的接口。

    参数:
    - body: ChatRequest, 聊天请求体
    - request: Request, FastAPI请求对象
    - session: 数据库会话
    - principal: 当前用户主体
    - resources: 资源依赖
    - settings: 应用设置

    返回:
    - ChatResponse, 聊天回复

    只有body是真正客户端传回来的请求数据，其余参数均由依赖注入提供。
    """
    return chat(session, principal, resources, settings, body, request.state.request_id)

