from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.exceptions import AppError
from app.db.models import User
from app.security.authentication import decode_token
from app.security.tenant_context import Principal

bearer = HTTPBearer(auto_error=False)


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def get_resources(request: Request):
    return request.app.state.resources


def get_settings_dependency(request: Request):
    return request.app.state.settings


def current_principal(
    request: Request, session=Depends(get_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None:
        raise AppError("UNAUTHORIZED", "请先登录", 401)
    claims = decode_token(credentials.credentials, request.app.state.settings)
    user = session.scalar(select(User).where(
        User.id == claims["sub"], User.tenant_id == claims["tenant_id"], User.is_active.is_(True),
    ))
    if user is None:
        raise AppError("UNAUTHORIZED", "账号不存在或已禁用", 401)
    return Principal(user.id, user.tenant_id, user.role)

