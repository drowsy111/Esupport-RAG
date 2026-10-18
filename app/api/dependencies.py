"""
文件说明: 该模块定义了FastAPI应用的依赖项，包括数据库会话、资源、设置以及当前用户的主体信息。
"""
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.exceptions import AppError
from app.db.models import User
from app.security.authentication import decode_token
from app.security.tenant_context import Principal

bearer = HTTPBearer(auto_error=False)


def get_session(request: Request):
    """
    获取数据库会话的依赖项。
    使用上下文管理器确保会话在使用后正确关闭。
    """
    with request.app.state.session_factory() as session:
        yield session


def get_resources(request: Request):
    """
    获取应用资源的依赖项。
    """
    return request.app.state.resources


def get_settings_dependency(request: Request):
    """
    获取应用设置的依赖项。
    """
    return request.app.state.settings


def current_principal(
    request: Request, session=Depends(get_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    """
    获取当前请求的主体信息（Principal）。

    如果请求中没有提供有效的JWT令牌，或者令牌对应的用户不存在或已禁用，将抛出AppError异常。

    返回值: Principal对象，包含用户ID、租户ID和角色信息。

    credentials.credentials == jwt.encode(claims, request.app.state.settings.jwt_secret.get_secret_value(), algorithm="HS256")
    decode_token()解析了jwt.encode，JWT令牌，返回其中的声明(claims)字典。
    """
    if credentials is None:
        raise AppError("UNAUTHORIZED", "请先登录", 401)
    claims = decode_token(credentials.credentials, request.app.state.settings)
    user = session.scalar(select(User).where(
        User.id == claims["sub"], User.tenant_id == claims["tenant_id"], User.is_active.is_(True),
    ))
    if user is None:
        raise AppError("UNAUTHORIZED", "账号不存在或已禁用", 401)
    return Principal(user.id, user.tenant_id, user.role)

